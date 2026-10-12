# EasyHuntV2: Standard Operating Procedure

AI-assisted property title scrutiny for Indian banks.
Encegen AI Labs, internal document. Rewritten 2026-10-12 to the attorney-approved 8-step flow.

---

## 1. Purpose

EasyHuntV2 automates the property title scrutiny work that lawyers carry out for Indian banks. It turns raw property documents into bank-ready scrutiny reports, with the ownership chain, key parties, and red flags clearly laid out.

---

## 2. Who is involved

| Role | Description |
|---|---|
| Borrower | A person applying to a bank for a home or property loan. Submits their property documents to the bank as part of the application. |
| Bank | Cannot approve a property loan without knowing the title is clean. Sends the borrower's documents to an empanelled lawyer for scrutiny, and needs the result back in its own specific report format. |
| Lawyer (attorney) | A legal professional specialising in property matters. Verifies ownership history, identifies disputes, and produces the scrutiny report. The only person who operates EasyHuntV2 day to day. In the database and API this role is named `Reviewer`; the screens call it "Lawyer". |
| Admin | Creates lawyer accounts and assigns cases. Does not do scrutiny. |

---

## 3. Why this exists

Today the lawyer reads every document manually. Many are handwritten, many are in a regional language. The lawyer traces ownership by hand across decades of records, then retypes the findings into whichever format that particular bank demands. It is slow, repetitive, and error-prone.

EasyHuntV2 does the reading, extraction, and formatting so the lawyer spends their time on judgement rather than transcription.

---

## 4. Documents handled

Property documents submitted by the borrower through the bank, including but not limited to:

- 7/12 extract
- Ferfar (mutation records)
- Sale deeds
- Partition deeds
- Gift deeds
- Tax receipts
- Encumbrance certificates
- Any other document establishing ownership, transfer, or encumbrance

Multiple documents belong to a single case. A case represents one property under scrutiny.

---

## 5. System flow

Each step unlocks the next. The lawyer works only on documents that have finished processing and that they have approved.

### Step 1: Upload
The lawyer creates a case and uploads its documents in a batch. After the upload the screen shows a notice asking the lawyer to check every extracted field against the original (spelling, names, numbers, dates) before approving.

### Step 2: Document identification and extraction
Every page is enhanced (deskew, contrast, noise reduction) and then identified.
- **2a. Handwritten** pages, or pages where OCR confidence is low, go to Gemini, which transcribes and digitises the content.
- **2b. Typed or printed** pages go to OCR, then on to extraction.

Tables in the source are kept as real tables. No stray `|` characters or `<br>` tags appear in the extracted text.

### Step 3: Document approval (per document)
The lawyer is shown each document next to what was extracted from it, with a translation, and approves each document individually.
- A document that has finished processing can be reviewed straight away; the lawyer does not wait for the rest of the batch.
- Handwritten content is always flagged for human verification.
- An approval can be undone. Un-approving a document removes it from search and from any report until it is approved again.

### Step 4: Search fields
Once at least one document is approved, the lawyer opens Search. A form asks for the details being scrutinised: survey / gat / CTS number, owner name, village or location, registration number, and free keywords.

### Step 5: Search results for verification
Search runs only over approved documents. The screen lists the exact matches and, separately, similar words (spelling variants, transliterations, near matches). The lawyer picks which exact and similar words they want; the documents then highlight those words in place. The lawyer selects the text and findings to carry into the report. Nothing reaches the report without the lawyer choosing it.

### Step 6: Choose what to produce
When the lawyer is satisfied with the extraction and selections for the documents in question, a report page opens with a dropdown:
1. **Title Search Report / Legal Search Report.**
2. **Bank format report.** Pick from the nine bank templates held by the system.
3. **Upload a bank format** to produce a report in the same layout. Shown as "Coming soon"; not available yet.

### Step 7: Review and edit the generated report
The generated report opens in the browser, editable. The lawyer can change any text and can go back to the selections and return. Fields that need legal judgement (opinion, marketability, adverse remarks, tenure) are never filled in for the lawyer; the lawyer writes or confirms them.

### Step 8: Download
Once approved, the lawyer downloads the report as Word or PDF.

---

## 6. Role of the LLM

The LLM is not a generic text extractor in this system. It is expected to operate with the knowledge and judgement of a property lawyer:

- Understand Indian property document types and what each one establishes
- Recognise what constitutes a break or gap in a chain of ownership
- Identify what legally counts as a red flag on a title
- Understand the significance of a mutation entry, an encumbrance, a partition
- Use legal terminology correctly and precisely, as a lawyer would

Its output is always a draft for a qualified lawyer to verify and approve. It never issues a final legal opinion on its own.

---

## 7. Core operating principles

- Nothing goes into a report without the lawyer selecting or approving it.
- Search and reports use approved documents only.
- Handwritten content is always flagged for human verification.
- The system assists judgement, it does not replace it.
- Reports must match the receiving bank's format exactly. That is the purpose of holding the bank templates.
- Accounts are created by an admin. There is no self-registration and no borrower or bank login.
