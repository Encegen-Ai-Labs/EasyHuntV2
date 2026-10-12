import httpx
import pytest

from app.core.config import settings
from app.services import translation_service as svc

KEY = "AQ.FakeKeyForTestsOnly000000000000000000"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    """No network, no real key, and a clean fallback timer for every test."""
    monkeypatch.setattr(svc, "_google_disabled_until", 0.0)
    monkeypatch.setattr(svc, "record_usage", lambda *a, **k: None, raising=False)
    import app.services.llm_usage as usage

    monkeypatch.setattr(usage, "record_usage", lambda *a, **k: None)
    monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "google")


class _Client:
    """Stands in for httpx.Client; `handler(url, headers, json)` returns a response or raises."""

    def __init__(self, handler):
        self.handler = handler

    def __call__(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, headers=None, json=None, params=None):
        assert params is None, "the API key must not travel in the URL"
        return self.handler(url, headers, json)


def _ok(text="some text"):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"translations": [{"translatedText": text}]}}

    return Response()


def _status_error(status, body=None, text=""):
    class Response:
        status_code = status

        def __init__(self):
            self.text = text

        def raise_for_status(self):
            request = httpx.Request("POST", f"{svc.GOOGLE_TRANSLATE_URL}?key={KEY}")
            raise httpx.HTTPStatusError(f"Client error '{status}' for url '{request.url}'", request=request, response=self)

        def json(self):
            if body is None:
                raise ValueError("not json")
            return body

    return Response()


def test_empty_text_short_circuits(monkeypatch):
    monkeypatch.setattr(httpx, "Client", lambda **k: pytest.fail("no request for empty text"))
    assert svc.translate_to_english("   ") == {"success": True, "translated_text": "", "error": None}


def test_google_only_mode_without_a_key_says_which_setting_is_missing(monkeypatch):
    monkeypatch.setattr(svc, "GOOGLE_TRANSLATE_API_KEY", None)
    result = svc.translate_to_english("कुछ पाठ")
    assert result["success"] is False and "GOOGLE_TRANSLATE_API_KEY" in result["error"]


def test_success_sends_the_key_in_a_header_not_the_url(monkeypatch):
    monkeypatch.setattr(svc, "GOOGLE_TRANSLATE_API_KEY", "test-key")
    seen = {}

    def handler(url, headers, json):
        seen.update(url=url, headers=headers, json=json)
        return _ok()

    monkeypatch.setattr(httpx, "Client", _Client(handler))
    result = svc.translate_to_english("कुछ पाठ")

    assert result["success"] and result["translated_text"] == "some text" and result["provider"] == "google"
    assert seen["headers"] == {"x-goog-api-key": "test-key"} and "key=" not in seen["url"]
    assert seen["json"]["target"] == "en" and "source" not in seen["json"]


def test_network_failure_fails_gracefully(monkeypatch):
    monkeypatch.setattr(svc, "GOOGLE_TRANSLATE_API_KEY", "test-key")

    def handler(url, headers, json):
        raise ConnectionError("network unreachable")

    monkeypatch.setattr(httpx, "Client", _Client(handler))
    result = svc.translate_to_english("कुछ पाठ")
    assert result["success"] is False and "network unreachable" in result["error"]


def test_a_rejected_key_error_shows_googles_reason_but_never_the_key(monkeypatch):
    monkeypatch.setattr(svc, "GOOGLE_TRANSLATE_API_KEY", KEY)
    body = {"error": {"code": 401, "message": "API keys are not supported by this API. Expected OAuth2 access token."}}
    monkeypatch.setattr(httpx, "Client", _Client(lambda *a: _status_error(401, body)))

    result = svc.translate_to_english("कुछ पाठ")

    assert result["success"] is False and result["auth_failed"] is True
    assert "API keys are not supported by this API" in result["error"]
    assert KEY not in result["error"] and "key=" not in result["error"] and "googleapis.com" not in result["error"]


def test_a_non_json_server_error_uses_the_response_text(monkeypatch):
    monkeypatch.setattr(svc, "GOOGLE_TRANSLATE_API_KEY", "test-key")
    monkeypatch.setattr(httpx, "Client", _Client(lambda *a: _status_error(500, None, "internal server error")))

    result = svc.translate_to_english("कुछ पाठ")
    assert "500" in result["error"] and "internal server error" in result["error"] and result["auth_failed"] is False


def test_auto_mode_falls_back_to_gemini_when_google_rejects_the_key(monkeypatch):
    monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "auto")
    monkeypatch.setattr(svc, "GOOGLE_TRANSLATE_API_KEY", KEY)
    calls = {"google": 0, "gemini": 0}

    def google_handler(*a):
        calls["google"] += 1
        return _status_error(401, {"error": {"message": "API keys are not supported by this API."}})

    monkeypatch.setattr(httpx, "Client", _Client(google_handler))

    def fake_gemini(text):
        calls["gemini"] += 1
        return {"success": True, "translated_text": "in English", "error": None, "provider": "gemini"}

    monkeypatch.setattr(svc, "_translate_gemini", fake_gemini)

    first = svc.translate_to_english("पहला")
    second = svc.translate_to_english("दूसरा")

    assert first["provider"] == "gemini" and second["provider"] == "gemini"
    assert calls == {"google": 1, "gemini": 2}  # the bad key is not retried for every page


def test_auto_mode_without_a_google_key_goes_straight_to_gemini(monkeypatch):
    monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "auto")
    monkeypatch.setattr(svc, "GOOGLE_TRANSLATE_API_KEY", None)
    monkeypatch.setattr(svc, "_translate_gemini", lambda text: {"success": True, "translated_text": "ok", "error": None, "provider": "gemini"})
    assert svc.translate_to_english("पाठ")["provider"] == "gemini"


def test_gemini_failures_are_scrubbed(monkeypatch):
    monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-secret-value-123")

    class FakeModels:
        def generate_content(self, **kwargs):
            raise RuntimeError("denied for gemini-key-secret-value-123")

    class FakeClient:
        models = FakeModels()

    import app.services.llm_extractor as extractor

    monkeypatch.setattr(extractor, "client_genai", FakeClient())
    result = svc.translate_to_english("पाठ")
    assert result["success"] is False and "gemini-key-secret-value-123" not in result["error"]


def test_translate_pages_stores_a_short_marker_without_secrets(monkeypatch):
    monkeypatch.setattr(
        svc, "translate_to_english",
        lambda text: {"success": False, "translated_text": None, "error": f"bad url ?key={KEY}"},
    )
    page = svc.translate_pages([{"page_number": 1, "original_text": "पाठ"}])[0]
    assert page["english_text"].startswith("[translation failed") and KEY not in page["english_text"]


def test_translate_pages_keeps_going_after_one_failure(monkeypatch):
    results = iter([
        {"success": True, "translated_text": "one", "error": None},
        {"success": False, "translated_text": None, "error": "boom"},
        {"success": True, "translated_text": "three", "error": None},
    ])
    monkeypatch.setattr(svc, "translate_to_english", lambda text: next(results))
    pages = svc.translate_pages([{"page_number": i, "original_text": "x"} for i in (1, 2, 3)])
    assert [p["english_text"] for p in pages] == ["one", "[translation failed: boom]", "three"]
