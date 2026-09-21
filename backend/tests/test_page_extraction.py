import io

import fitz
import httpx
import pytest
from PIL import Image

from app.services import page_extraction_service as page_svc


def _make_pdf_bytes(page_count: int) -> bytes:
    doc = fitz.open()
    for i in range(page_count):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} content")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_png_bytes(size=(100, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color="white").save(buf, format="PNG")
    return buf.getvalue()


def test_rasterize_pages_normalizes_single_image_to_png():
    # Uploads that aren't PDFs (any image format) are treated as one page,
    # normalized to PNG so downstream enhancement/OCR/VLM always see PNG.
    jpeg_buf = io.BytesIO()
    Image.new("RGB", (50, 50), color="blue").save(jpeg_buf, format="JPEG")

    result = page_svc.rasterize_pages(jpeg_buf.getvalue(), "image/jpeg")

    assert len(result) == 1
    img = Image.open(io.BytesIO(result[0]))
    assert img.format == "PNG"
    assert img.size == (50, 50)


def test_rasterize_pages_caps_oversized_image_dimensions():
    # A raw phone-photo upload has no equivalent to RASTER_DPI's deliberate
    # size cap for PDFs — left uncapped, a 4000px+ photo re-encoded to
    # lossless PNG (and then color-enhanced) can balloon to tens of MB,
    # which is slow enough to upload/process that it can exhaust the VLM
    # call's own timeout on a page with nothing actually wrong with it. See
    # MAX_IMAGE_DIMENSION_PX's comment in page_extraction_service.py.
    huge_buf = io.BytesIO()
    Image.new("RGB", (6000, 4000), color="white").save(huge_buf, format="JPEG")

    result = page_svc.rasterize_pages(huge_buf.getvalue(), "image/jpeg")

    img = Image.open(io.BytesIO(result[0]))
    assert max(img.size) == page_svc.MAX_IMAGE_DIMENSION_PX
    # Aspect ratio (3:2 here) preserved, not stretched/squashed.
    assert img.size[0] / img.size[1] == pytest.approx(6000 / 4000, rel=0.01)


def test_rasterize_pages_never_upscales_a_smaller_image():
    small_buf = io.BytesIO()
    Image.new("RGB", (200, 150), color="white").save(small_buf, format="JPEG")

    result = page_svc.rasterize_pages(small_buf.getvalue(), "image/jpeg")

    img = Image.open(io.BytesIO(result[0]))
    assert img.size == (200, 150)


def test_rasterize_pages_caps_oversized_pdf_page():
    # A PDF's MediaBox isn't always a normal A4/Letter size — a
    # large-format/poster-sized page (or a high-res scan embedded on an
    # oversized page) rendered at the fixed RASTER_DPI still comes out
    # proportionally oversized. Reproduces the real failure this was built
    # for: a ~1606x2365pt (~22x33in) page rasterized to 4463x6569px at
    # 200 DPI — an 11.9MB PNG that ballooned to 44MB after enhancement and
    # consistently defeated Gemini's vision endpoint (504, every retry).
    doc = fitz.open()
    doc.new_page(width=1606.5, height=2364.8)
    pdf_bytes = doc.tobytes()
    doc.close()

    result = page_svc.rasterize_pages(pdf_bytes, "application/pdf")

    img = Image.open(io.BytesIO(result[0]))
    assert max(img.size) <= page_svc.MAX_IMAGE_DIMENSION_PX
    assert img.size[0] / img.size[1] == pytest.approx(1606.5 / 2364.8, rel=0.01)


def test_rasterize_pages_normal_pdf_page_unaffected_by_dpi_cap():
    # A standard-size page (well within the cap even at the full
    # RASTER_DPI) should render exactly as it always did — the cap formula
    # should never raise the DPI above RASTER_DPI, only lower it.
    pdf_bytes = _make_pdf_bytes(1)

    result = page_svc.rasterize_pages(pdf_bytes, "application/pdf")

    img = Image.open(io.BytesIO(result[0]))
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_width_pt, page_height_pt = doc[0].rect.width, doc[0].rect.height
    doc.close()
    expected_w = round(page_width_pt / 72 * page_svc.RASTER_DPI)
    expected_h = round(page_height_pt / 72 * page_svc.RASTER_DPI)
    assert img.size == (expected_w, expected_h)


def test_rasterize_pages_single_page_pdf_still_rasterizes():
    # No more "reuse whole-document text" shortcut for 1-page PDFs — every
    # page always gets rasterized now, since each page is independently
    # routed to OCR or the VLM.
    pdf_bytes = _make_pdf_bytes(1)
    result = page_svc.rasterize_pages(pdf_bytes, "application/pdf")

    assert len(result) == 1
    img = Image.open(io.BytesIO(result[0]))
    assert img.format == "PNG"


def test_rasterize_pages_returns_one_image_per_pdf_page():
    pdf_bytes = _make_pdf_bytes(3)
    result = page_svc.rasterize_pages(pdf_bytes, "application/pdf")

    assert len(result) == 3
    for page_bytes in result:
        img = Image.open(io.BytesIO(page_bytes))
        assert img.format == "PNG"


def test_download_and_rasterize_downloads_then_splits(monkeypatch):
    pdf_bytes = _make_pdf_bytes(2)

    class FakeResponse:
        content = pdf_bytes

        def raise_for_status(self):
            pass

    class FakeHttpxClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", lambda: FakeHttpxClient())

    result = page_svc.download_and_rasterize("https://example.com/file.pdf", "application/pdf")

    assert len(result) == 2


def test_download_and_rasterize_raises_on_download_error(monkeypatch):
    # Unlike the old page-extraction step this replaces, rasterization now
    # happens before any per-page routing/extraction has started, so there's
    # nothing partial to protect — the caller (pipeline_service.py) catches
    # this the same way it already handles other early-pipeline failures.
    class FailingHttpxClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            raise ConnectionError("network unreachable")

    monkeypatch.setattr(httpx, "Client", lambda: FailingHttpxClient())

    with pytest.raises(ConnectionError):
        page_svc.download_and_rasterize("https://example.com/file.pdf", "application/pdf")


def test_extract_page_text_success(monkeypatch):
    class FakeResponse:
        text = "  transcribed text  "

    monkeypatch.setattr(
        page_svc.client_genai.models, "generate_content", lambda **kwargs: FakeResponse()
    )

    result = page_svc.extract_page_text(_make_png_bytes(), mime_type="image/png")

    assert result == {"success": True, "text": "transcribed text", "error": None}


def test_extract_page_text_failure_returns_sentinel(monkeypatch):
    def _raise(**kwargs):
        raise RuntimeError("Gemini timeout")

    monkeypatch.setattr(page_svc.client_genai.models, "generate_content", _raise)

    result = page_svc.extract_page_text(_make_png_bytes(), mime_type="image/png")

    assert result["success"] is False
    assert "Gemini timeout" in result["error"]


def test_strip_annotation_tags_removes_known_tag_kinds():
    text = (
        "Survey No. 123, village Rampur.\n"
        "[Signature: Handwritten]\n"
        "[Stamp: Received 12-Oct]\n"
        "[Checkbox: Checked] Consent given\n"
        '[Handwritten note: "Approved"]\n'
        "Total area: 5 acres"
    )

    result = page_svc.strip_annotation_tags(text)

    assert "[Signature:" not in result
    assert "[Stamp:" not in result
    assert "[Checkbox:" not in result
    assert "[Handwritten note:" not in result
    assert "Survey No. 123, village Rampur." in result
    assert "Consent given" in result
    assert "Total area: 5 acres" in result


def test_strip_annotation_tags_keeps_illegible_marker():
    # [illegible] is meaningful inline content (marks a transcription gap),
    # not a structural annotation — must survive stripping unlike the
    # signature/stamp/checkbox/handwritten-note tags above.
    text = "Owner name: [illegible], son of Ramesh"

    result = page_svc.strip_annotation_tags(text)

    assert "[illegible]" in result


def test_strip_annotation_tags_handles_empty_and_none():
    assert page_svc.strip_annotation_tags("") == ""
    assert page_svc.strip_annotation_tags(None) is None


def test_strip_annotation_tags_collapses_blank_lines_left_by_removed_tags():
    text = "Line one\n\n[Stamp: Received]\n\nLine two"

    result = page_svc.strip_annotation_tags(text)

    assert "\n\n\n" not in result
    assert "Line one" in result
    assert "Line two" in result
