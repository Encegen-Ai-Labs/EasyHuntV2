"""Rules this application depends on, checked on every change.

These are not behaviour tests of one feature: each one protects something that
would hurt a lawyer, a bank, or the budget if a future change quietly broke it.
"""
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app.dependencies.auth import get_current_user
from app.main import app
from app.services import report_formats

BACKEND = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND / "app"

# The only endpoints a stranger may call. Everything else needs a signed-in user.
PUBLIC_PATHS = {"/", "/health", "/health/ready", "/api/v1/auth/login", "/api/v1/health"}


def _needs_login(dependant) -> bool:
    for dependency in dependant.dependencies:
        if dependency.call is get_current_user or _needs_login(dependency):
            return True
    return False


def test_every_endpoint_except_the_public_ones_requires_a_signed_in_user():
    open_routes = [
        f"{sorted(route.methods)[0]} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute) and route.path not in PUBLIC_PATHS and not _needs_login(route.dependant)
    ]
    assert open_routes == [], f"endpoints reachable without logging in: {open_routes}"


def _python_files():
    return [p for p in APP_DIR.rglob("*.py") if "__pycache__" not in p.parts]


def test_every_model_call_goes_through_the_cost_tracker():
    # A call made directly would spend money with no record and no daily limit.
    direct = re.compile(r"\.models\.(generate_content|embed_content)\(")
    offenders = [
        str(p.relative_to(BACKEND))
        for p in _python_files()
        if p.name != "llm_usage.py" and direct.search(p.read_text(encoding="utf-8-sig"))
    ]
    assert offenders == [], f"call generate_tracked() instead in: {offenders}"


def test_no_api_key_is_ever_put_in_a_url():
    # An error message includes the URL it failed on, so a key in it would be logged and shown.
    pattern = re.compile(r"""params\s*=\s*\{\s*["'](key|api_key|token)["']|[?&](key|api_key)=\{""")
    offenders = [str(p.relative_to(BACKEND)) for p in _python_files() if pattern.search(p.read_text(encoding="utf-8-sig"))]
    assert offenders == [], f"send keys in a header, not the URL: {offenders}"


# ---- bank templates ----

BANK_IDS = [f["id"] for f in report_formats.list_formats() if f["kind"] == "bank"]


@pytest.mark.parametrize("format_id", BANK_IDS)
def test_a_bank_template_and_its_field_list_agree(format_id):
    """A field the template prints but the list does not know is never filled; a
    field in the list that the template never prints is asked for and then lost."""
    from docxtpl import DocxTemplate

    manifest = report_formats.get_manifest(format_id)
    declared = {f["name"] for f in manifest["fields"]} | {l["name"] for l in manifest["loops"]}
    used = DocxTemplate(str(report_formats.template_path(format_id))).get_undeclared_template_variables()

    assert used - declared == set(), f"{format_id}: in the template but not in the field list: {sorted(used - declared)}"
    assert declared - used == set(), f"{format_id}: in the field list but never printed: {sorted(declared - used)}"


# ---- migrations ----

MIGRATIONS = sorted((BACKEND / "migrations").glob("[0-9][0-9][0-9][0-9]_*.sql"))


def test_migrations_are_numbered_without_gaps_or_repeats():
    numbers = [int(m.name[:4]) for m in MIGRATIONS]
    assert numbers == list(range(numbers[0], numbers[0] + len(numbers))), f"migration numbers: {numbers}"


@pytest.mark.parametrize("path", MIGRATIONS, ids=lambda p: p.name)
def test_a_migration_can_be_run_twice_and_destroys_nothing(path):
    sql = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8-sig")).lower()
    for statement in re.findall(r"create\s+(?:unique\s+)?(?:table|index|extension)\s+(?!if\s+not\s+exists)[^\n;]*", sql):
        pytest.fail(f"{path.name}: needs IF NOT EXISTS: {statement.strip()}")
    destructive = re.findall(r"\b(drop\s+table|drop\s+column|truncate|delete\s+from)\b", sql)
    allowed = "destructive-ok" in path.read_text(encoding="utf-8-sig").lower()
    assert not destructive or allowed, (
        f"{path.name} removes data ({destructive}). Releases only add; remove things in a later release "
        "and mark the file with a '-- destructive-ok: <why>' comment."
    )
