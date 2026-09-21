import httpx

from app.services import translation_service as translation_svc


def test_empty_text_short_circuits_without_calling_the_api(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("httpx.Client should not be constructed for empty text")

    monkeypatch.setattr(httpx, "Client", _fail_if_called)

    result = translation_svc.translate_to_english("   ")

    assert result == {"success": True, "translated_text": "", "error": None}


def test_missing_api_key_fails_gracefully(monkeypatch):
    monkeypatch.setattr(translation_svc, "GOOGLE_TRANSLATE_API_KEY", None)

    result = translation_svc.translate_to_english("कुछ पाठ")

    assert result["success"] is False
    assert "GOOGLE_TRANSLATE_API_KEY" in result["error"]


def test_successful_translation_returns_translated_text(monkeypatch):
    monkeypatch.setattr(translation_svc, "GOOGLE_TRANSLATE_API_KEY", "test-key")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": {"translations": [{"translatedText": "some text"}]}}

    class FakeHttpxClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, params=None, json=None):
            assert params["key"] == "test-key"
            assert json["target"] == "en"
            assert "source" not in json  # source language is left to auto-detect
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", lambda: FakeHttpxClient())

    result = translation_svc.translate_to_english("कुछ पाठ")

    assert result == {"success": True, "translated_text": "some text", "error": None}


def test_api_error_fails_gracefully_without_raising(monkeypatch):
    monkeypatch.setattr(translation_svc, "GOOGLE_TRANSLATE_API_KEY", "test-key")

    class FailingHttpxClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, params=None, json=None):
            raise ConnectionError("network unreachable")

    monkeypatch.setattr(httpx, "Client", lambda: FailingHttpxClient())

    result = translation_svc.translate_to_english("कुछ पाठ")

    assert result["success"] is False
    assert "network unreachable" in result["error"]


def test_http_status_error_surfaces_googles_error_message(monkeypatch):
    monkeypatch.setattr(translation_svc, "GOOGLE_TRANSLATE_API_KEY", "test-key")

    class FakeResponse:
        status_code = 401

        def raise_for_status(self):
            request = httpx.Request("POST", translation_svc.GOOGLE_TRANSLATE_URL)
            raise httpx.HTTPStatusError(
                "Client error '401 Unauthorized'", request=request, response=self
            )

        def json(self):
            return {
                "error": {
                    "code": 401,
                    "message": "API keys are not supported by this API. Expected OAuth2 access token.",
                    "status": "UNAUTHENTICATED",
                }
            }

    class FakeHttpxClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, params=None, json=None):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", lambda: FakeHttpxClient())

    result = translation_svc.translate_to_english("कुछ पाठ")

    assert result["success"] is False
    assert "API keys are not supported by this API" in result["error"]


def test_http_status_error_falls_back_to_response_text_when_body_not_json(monkeypatch):
    monkeypatch.setattr(translation_svc, "GOOGLE_TRANSLATE_API_KEY", "test-key")

    class FakeResponse:
        status_code = 500
        text = "internal server error"

        def raise_for_status(self):
            request = httpx.Request("POST", translation_svc.GOOGLE_TRANSLATE_URL)
            raise httpx.HTTPStatusError(
                "Server error '500 Internal Server Error'", request=request, response=self
            )

        def json(self):
            raise ValueError("not json")

    class FakeHttpxClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, params=None, json=None):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", lambda: FakeHttpxClient())

    result = translation_svc.translate_to_english("कुछ पाठ")

    assert result["success"] is False
    assert "internal server error" in result["error"]


def test_translate_pages_adds_english_text_per_page(monkeypatch):
    def fake_translate(text):
        return {"success": True, "translated_text": text.upper(), "error": None}

    monkeypatch.setattr(translation_svc, "translate_to_english", fake_translate)

    pages = [
        {"page_number": 1, "original_text": "hello"},
        {"page_number": 2, "original_text": "world"},
    ]
    result = translation_svc.translate_pages(pages)

    assert result == [
        {"page_number": 1, "original_text": "hello", "english_text": "HELLO"},
        {"page_number": 2, "original_text": "world", "english_text": "WORLD"},
    ]


def test_translate_pages_records_failure_sentinel_without_stopping_other_pages(monkeypatch):
    def flaky_translate(text):
        if text == "bad":
            return {"success": False, "translated_text": None, "error": "quota exceeded"}
        return {"success": True, "translated_text": text.upper(), "error": None}

    monkeypatch.setattr(translation_svc, "translate_to_english", flaky_translate)

    pages = [
        {"page_number": 1, "original_text": "bad"},
        {"page_number": 2, "original_text": "good"},
    ]
    result = translation_svc.translate_pages(pages)

    assert "translation failed" in result[0]["english_text"]
    assert "quota exceeded" in result[0]["english_text"]
    assert result[1]["english_text"] == "GOOD"
