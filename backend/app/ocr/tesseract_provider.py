"""Tesseract-backed OCR provider.

Confidence-based handwriting hint: a word's `is_handwritten` is set when
Tesseract's own recognition confidence for that word falls below
HANDWRITING_CONFIDENCE_HINT — see the caveat on TextBox.is_handwritten in
provider.py, this is a proxy signal, not a real handwriting classifier.
"""

from __future__ import annotations

import io

from PIL import Image

from app.core.config import settings
from .provider import BoundingBox, OcrPageResult, TextBox

# Tesseract word confidence is 0..100; below this, the router's caller treats
# a box as "likely handwritten" rather than "OCR just did a bad job".
HANDWRITING_CONFIDENCE_HINT = 60.0


class TesseractOcrProvider:
    """Wraps pytesseract.image_to_data for word-level boxes + confidences."""

    def __init__(self):
        import pytesseract  # noqa: F401  (import check — raises if not installed)
        if settings.TESSERACT_CMD_PATH:
            import pytesseract as pt
            pt.pytesseract.tesseract_cmd = settings.TESSERACT_CMD_PATH
        self._handwriting_hint = HANDWRITING_CONFIDENCE_HINT
        self._lang = self._resolve_languages()

    @staticmethod
    def _resolve_languages() -> str:
        """Intersects settings.TESSERACT_LANGUAGES with whatever language
        packs are actually installed, instead of using the configured value
        as-is. pytesseract raises outright if asked for a language pack that
        isn't installed — with no intersection, requesting a language that
        isn't there yet would break OCR for *every* page (including ones in
        languages Tesseract can already read fine), forcing all of them to
        the VLM instead of just the ones that genuinely need it. Falls back
        to "eng" alone if even that intersection comes up empty (or the
        installed-languages query itself fails) — some working language is
        better than none."""
        import pytesseract
        desired = [lang for lang in settings.TESSERACT_LANGUAGES.split("+") if lang]
        try:
            installed = set(pytesseract.get_languages(config=""))
        except Exception:
            return "eng"
        available = [lang for lang in desired if lang in installed]
        return "+".join(available) if available else "eng"

    @property
    def name(self) -> str:
        return "tesseract"

    def is_available(self) -> bool:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def detect_and_recognize(self, image_bytes: bytes) -> OcrPageResult:
        import pytesseract

        try:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            return OcrPageResult(error=f"failed to decode image: {e}", engine=self.name)

        width, height = pil_img.size

        try:
            data = pytesseract.image_to_data(
                pil_img,
                lang=self._lang,
                output_type=pytesseract.Output.DICT,
                config="--psm 3",  # automatic page segmentation, no OSD
            )
        except Exception as e:
            return OcrPageResult(
                error=f"tesseract.image_to_data() raised: {e}",
                page_width=width, page_height=height, engine=self.name,
            )

        boxes: list[TextBox] = []
        total_area = 0
        weighted_conf_sum = 0.0
        text_parts: list[str] = []

        n = len(data["text"])
        for i in range(n):
            text = data["text"][i].strip()
            if not text:
                continue
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                continue
            if conf < 0:
                continue  # Tesseract uses -1 for non-text regions

            w = int(data["width"][i])
            h = int(data["height"][i])
            if w <= 0 or h <= 0:
                continue

            conf01 = conf / 100.0
            bbox = BoundingBox(x=int(data["left"][i]), y=int(data["top"][i]), w=w, h=h)

            boxes.append(TextBox(
                bbox=bbox, text=text, confidence=conf01,
                is_handwritten=conf < self._handwriting_hint,
            ))
            total_area += bbox.area
            weighted_conf_sum += conf01 * bbox.area
            text_parts.append(text)

        overall = (weighted_conf_sum / total_area) if total_area > 0 else 0.0
        return OcrPageResult(
            boxes=boxes,
            full_text=" ".join(text_parts),
            overall_confidence=overall,
            page_width=width,
            page_height=height,
            engine=self.name,
        )
