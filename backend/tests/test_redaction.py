import httpx

from app.core.redaction import REDACTED, redact, safe_error


def test_a_failed_translation_url_does_not_keep_its_key():
    text = "Client error '401 Unauthorized' for url 'https://translation.googleapis.com/language/translate/v2?key=AQ.FakeKeyForTestsOnly000000000000000000'"
    cleaned = redact(text)
    assert "AQ.Fak" not in cleaned and "key=" + REDACTED in cleaned


def test_configured_secret_values_are_scrubbed_in_any_shape(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "plain-looking-secret-value-123")
    assert redact("boom: plain-looking-secret-value-123 rejected") == f"boom: {REDACTED} rejected"


def test_short_env_values_are_ignored(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "abc")
    assert redact("abc def") == "abc def"


def test_bearer_tokens_and_jwts_and_known_key_shapes():
    jwt = ".".join(["eyJ" + "hbGciOiJIUzI1NiJ9", "eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0", "abcdefghijklmnop"])  # built, not written out: a literal trips secret scanners
    assert jwt not in redact(f"token {jwt}")
    assert "abcdefghijklmnop12345" not in redact("Authorization: Bearer abcdefghijklmnop12345")
    assert "AIzaSyA1234567890abcdefghijklmnop" not in redact("AIzaSyA1234567890abcdefghijklmnop")
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in redact("sk-abcdefghijklmnopqrstuvwxyz")


def test_ordinary_text_and_none_are_unchanged():
    assert redact("Survey number 12/3, key in the lock") == "Survey number 12/3, key in the lock"
    assert redact(None) == ""


def test_an_httpx_status_error_message_is_cleaned_by_safe_error():
    request = httpx.Request("POST", "https://example.test/v2?key=SUPERSECRETKEYVALUE12345")
    response = httpx.Response(401, request=request)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        cleaned = safe_error(error)
    assert "SUPERSECRETKEYVALUE12345" not in cleaned and cleaned.startswith("HTTPStatusError")
