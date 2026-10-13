"""Load test: several lawyers using a RUNNING server at the same time.

    python scripts/load_test.py --base-url http://localhost:8000 \
        --admin-email admin@example.com --admin-password '...' --users 6 --docs 20

Each simulated lawyer does what a real one does: log in, create a case, upload a
batch of documents, then keep using the app (open the case, list documents, open
the review list) while the server is still reading the batch, and finally approve
every document. Afterwards it prints, per request type, how many succeeded and how
long they took, and how long the whole batch took to be read.

WARNING: this is a real run. Every uploaded document goes through the real
pipeline, so it uses Gemini (money) and writes real rows to the real database.
Point it at a staging copy, start small (--users 2 --docs 3), and read the
Usage screen afterwards. Test accounts are named loadtest-*@example.com and cases
"LOADTEST ..."; --cleanup deletes the uploaded documents when the run ends.

It only needs httpx and PyMuPDF, both already in requirements.txt.
"""
import argparse
import asyncio
import os
import statistics
import sys
import time
import uuid
from collections import defaultdict
from typing import Dict, List, Optional

import fitz  # PyMuPDF: used to make small, distinct, readable PDFs
import httpx

IN_PROGRESS = {"uploaded", "processing", "ocr_done"}
APPROVED = {"approved", "completed"}


class Stats:
    def __init__(self) -> None:
        self.durations: Dict[str, List[float]] = defaultdict(list)
        self.failures: Dict[str, List[str]] = defaultdict(list)

    async def timed(self, name: str, call) -> Optional[httpx.Response]:
        started = time.monotonic()
        try:
            response = await call()
        except Exception as exc:  # network error, timeout
            self.durations[name].append(time.monotonic() - started)
            self.failures[name].append(f"{type(exc).__name__}: {exc}")
            return None
        self.durations[name].append(time.monotonic() - started)
        if response.status_code >= 400:
            self.failures[name].append(f"HTTP {response.status_code}: {response.text[:120]}")
        return response

    def report(self) -> int:
        print(f"\n{'request':<26}{'count':>7}{'failed':>8}{'p50 s':>8}{'p95 s':>8}{'max s':>8}")
        total_failed = 0
        for name in sorted(self.durations):
            times = sorted(self.durations[name])
            p95 = times[min(len(times) - 1, int(len(times) * 0.95))]
            failed = len(self.failures[name])
            total_failed += failed
            print(f"{name:<26}{len(times):>7}{failed:>8}{statistics.median(times):>8.2f}{p95:>8.2f}{times[-1]:>8.2f}")
        if total_failed:
            print("\nFirst failures per request type:")
            for name, items in self.failures.items():
                for item in sorted(set(items))[:3]:
                    print(f"  {name}: {item}")
        return total_failed


def make_pdf(label: str, pages: int) -> bytes:
    """A small printed-looking PDF whose text is unique, so the extraction cache
    (when on) cannot answer it and the full pipeline really runs."""
    pdf = fitz.open()
    for page_number in range(1, pages + 1):
        page = pdf.new_page()
        text = (
            f"SALE DEED {label} page {page_number}\n\n"
            f"This deed is made between Seller {label} and Buyer {uuid.uuid4().hex[:8]}\n"
            f"concerning Survey No. {abs(hash(label)) % 900 + 100}/{page_number} situated at Pune.\n"
            "The consideration was Rs. 25,00,000 paid in full. Dated 12/03/2019."
        )
        page.insert_textbox(fitz.Rect(60, 80, 540, 700), text, fontsize=12)
    data = pdf.tobytes()
    pdf.close()
    return data


async def lawyer(index: int, args, stats: Stats, email: str, password: str, outcome: dict) -> None:
    async with httpx.AsyncClient(base_url=args.base_url, timeout=args.timeout) as client:
        login = await stats.timed("login", lambda: client.post("/api/v1/auth/login", json={"email": email, "password": password}))
        if login is None or login.status_code != 200:
            return
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

        created = await stats.timed("create case", lambda: client.post(
            "/api/v1/cases", json={"property_name": f"LOADTEST {index}", "survey_number": "1/1", "location": "Pune"}))
        if created is None or created.status_code >= 400:
            return
        case_id = created.json()["id"]

        files = [
            ("files", (f"loadtest-{index}-{n}.pdf", make_pdf(f"{index}-{n}", args.pages), "application/pdf"))
            for n in range(args.docs)
        ]
        uploaded = await stats.timed("upload batch", lambda: client.post(
            "/api/v1/documents/upload", data={"case_id": case_id}, files=files))
        if uploaded is None or uploaded.status_code >= 400:
            return
        doc_ids = [r["document"]["id"] for r in uploaded.json()["results"] if r.get("success")]
        outcome["uploaded"] += len(doc_ids)
        started = time.monotonic()

        # While the server reads the batch, behave like a lawyer who is looking around.
        deadline = started + args.max_wait
        documents: List[dict] = []
        while time.monotonic() < deadline:
            listing = await stats.timed("list documents", lambda: client.get("/api/v1/documents", params={"case_id": case_id}))
            await stats.timed("open case", lambda: client.get(f"/api/v1/cases/{case_id}"))
            await stats.timed("list cases", lambda: client.get("/api/v1/cases"))
            if listing is not None and listing.status_code == 200:
                documents = listing.json()
                if not any(d["status"] in IN_PROGRESS for d in documents):
                    break
            await asyncio.sleep(args.poll)
        else:
            outcome["timed_out"] += 1
        outcome["read_seconds"].append(time.monotonic() - started)

        review = await stats.timed("review list", lambda: client.get(f"/api/v1/review/{case_id}/documents"))
        if review is None or review.status_code != 200:
            return
        for entry in review.json():
            extraction = entry.get("extraction")
            if not extraction:
                # Read to the end but nothing was produced: the document really failed.
                # (Status alone cannot say: "flagged" is also where every successfully
                # read document lands, because a lawyer must always check it.)
                outcome["no_result"] += 1
                continue
            fields = extraction.get("validated_json_output") or {}
            response = await stats.timed("approve document", lambda e=entry, f=fields: client.patch(
                f"/api/v1/review/documents/{e['document']['id']}",
                json={"validated_output": f, "decision": "approved"}))
            if response is not None and response.status_code < 400:
                outcome["approved"] += 1

        if args.cleanup:
            for document_id in doc_ids:
                await stats.timed("delete document", lambda d=document_id: client.delete(f"/api/v1/documents/{d}"))


async def main(args) -> int:
    stats = Stats()
    run_id = uuid.uuid4().hex[:6]
    password = "LoadTest-" + uuid.uuid4().hex[:10]
    outcome = {"uploaded": 0, "approved": 0, "timed_out": 0, "no_result": 0, "read_seconds": []}

    async with httpx.AsyncClient(base_url=args.base_url, timeout=args.timeout) as admin:
        login = await admin.post("/api/v1/auth/login", json={"email": args.admin_email, "password": args.admin_password})
        if login.status_code != 200:
            print(f"Admin login failed ({login.status_code}). Check --admin-email / --admin-password.")
            return 2
        admin.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        accounts = []
        for n in range(args.users):
            email = f"loadtest-{run_id}-{n}@example.com"
            made = await admin.post("/api/v1/admin/reviewers", json={
                "email": email, "password": password, "organisation_name": "LOADTEST"})
            if made.status_code >= 400:
                print(f"Could not create test lawyer {email}: {made.status_code} {made.text[:120]}")
                return 2
            accounts.append(email)

    print(f"{args.users} lawyers x {args.docs} documents x {args.pages} page(s) against {args.base_url} ...")
    started = time.monotonic()
    await asyncio.gather(*(lawyer(i, args, stats, accounts[i], password, outcome) for i in range(args.users)))
    elapsed = time.monotonic() - started

    failed = stats.report()
    reads = outcome["read_seconds"]
    print(f"\nWhole run: {elapsed:.0f}s. Uploaded {outcome['uploaded']} documents, approved {outcome['approved']}.")
    if reads:
        print(f"Time for a batch to finish being read: median {statistics.median(reads):.0f}s, slowest {max(reads):.0f}s.")
    if outcome["no_result"]:
        print(f"{outcome['no_result']} documents finished with no extracted result - check the Errors and Usage screens.")
    if outcome["timed_out"]:
        print(f"{outcome['timed_out']} lawyers hit --max-wait ({args.max_wait}s) before their batch finished.")
    expected = args.users * args.docs
    ok = failed == 0 and outcome["uploaded"] == expected and not outcome["timed_out"] and not outcome["no_result"]
    ok = ok and outcome["approved"] == expected
    print("\nRESULT:", "PASS" if ok else "FAIL (see above)")
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--admin-email", default=os.environ.get("LOADTEST_ADMIN_EMAIL"))
    parser.add_argument("--admin-password", default=os.environ.get("LOADTEST_ADMIN_PASSWORD"))
    parser.add_argument("--users", type=int, default=6)
    parser.add_argument("--docs", type=int, default=20, help="documents per user (max 20 per upload)")
    parser.add_argument("--pages", type=int, default=2, help="pages per document")
    parser.add_argument("--poll", type=float, default=3.0, help="seconds between a lawyer's refreshes")
    parser.add_argument("--max-wait", type=float, default=1800, help="give up waiting for a batch after this many seconds")
    parser.add_argument("--timeout", type=float, default=120, help="per-request timeout in seconds")
    parser.add_argument("--cleanup", action="store_true", help="delete the uploaded documents afterwards")
    parsed = parser.parse_args()
    if not parsed.admin_email or not parsed.admin_password:
        parser.error("--admin-email and --admin-password (or LOADTEST_ADMIN_EMAIL / LOADTEST_ADMIN_PASSWORD) are required")
    if not 1 <= parsed.docs <= 20:
        parser.error("--docs must be between 1 and 20")
    sys.exit(asyncio.run(main(parsed)))
