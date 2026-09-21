"""Tests for app/services/image_enhancement.py — synthetic images generated
in-memory (no live API calls), same pattern test_page_extraction.py uses for
synthetic PDFs."""

import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.image_enhancement import (
    CONTRAST_STD_LOW_THRESHOLD,
    NOISE_SIGMA_THRESHOLD,
    SHARPNESS_VARIANCE_THRESHOLD,
    _assess_quality,
    enhance_page_image,
)


def _make_low_contrast_page_png(skew_degrees: float = 0.0) -> bytes:
    """A synthetic "scanned page": light-gray text on an off-white background
    (low contrast), optionally rotated to simulate a skewed scan."""
    img = Image.new("L", (800, 1000), color=235)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()

    for i in range(15):
        draw.text((60, 60 + i * 50), f"Sale deed line {i} — property record text", fill=170, font=font)

    if skew_degrees:
        img = img.rotate(skew_degrees, fillcolor=235, expand=False)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def test_enhance_page_image_returns_valid_png_same_size():
    original = _make_low_contrast_page_png()
    enhanced = enhance_page_image(original)

    assert enhanced != b""
    orig_img = Image.open(io.BytesIO(original))
    enh_img = Image.open(io.BytesIO(enhanced))
    assert enh_img.size == orig_img.size


def test_enhance_page_image_improves_contrast():
    original = _make_low_contrast_page_png()
    enhanced = enhance_page_image(original)

    orig_arr = np.array(Image.open(io.BytesIO(original)).convert("L"))
    enh_arr = np.array(Image.open(io.BytesIO(enhanced)).convert("L"))

    # CLAHE should widen the pixel-intensity spread on a deliberately
    # low-contrast synthetic page (text drawn at 170 on a 235 background).
    assert enh_arr.std() > orig_arr.std()


def test_enhance_page_image_deskews_rotated_page():
    from app.services.image_enhancement import _estimate_skew_angle
    import cv2

    skewed = _make_low_contrast_page_png(skew_degrees=8.0)
    enhanced = enhance_page_image(skewed)

    skewed_gray = cv2.cvtColor(
        np.array(Image.open(io.BytesIO(skewed)).convert("RGB")), cv2.COLOR_RGB2GRAY
    )
    enhanced_gray = np.array(Image.open(io.BytesIO(enhanced)).convert("L"))

    angle_before = abs(_estimate_skew_angle(skewed_gray))
    angle_after = abs(_estimate_skew_angle(enhanced_gray))
    assert angle_after < angle_before


def test_enhance_page_image_falls_back_to_original_on_bad_input():
    garbage = b"not a real png"
    result = enhance_page_image(garbage)
    assert result == garbage


def _make_high_contrast_sharp_page_png() -> bytes:
    """A synthetic "clean" page: crisp black text on a pure white
    background, unskewed, with no added noise — the adaptive assessment
    should read this as already good quality and leave it largely alone."""
    img = Image.new("L", (800, 1000), color=255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()

    for i in range(15):
        draw.text((60, 60 + i * 50), f"Sale deed line {i} — property record text", fill=0, font=font)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def test_assess_quality_distinguishes_low_and_high_contrast_pages():
    low_gray = np.array(Image.open(io.BytesIO(_make_low_contrast_page_png())).convert("L"))
    high_gray = np.array(Image.open(io.BytesIO(_make_high_contrast_sharp_page_png())).convert("L"))

    low_metrics = _assess_quality(low_gray)
    high_metrics = _assess_quality(high_gray)

    assert low_metrics.contrast < CONTRAST_STD_LOW_THRESHOLD
    assert high_metrics.contrast >= CONTRAST_STD_LOW_THRESHOLD
    # Neither synthetic page has added noise, so both should read as clean.
    assert low_metrics.noise_sigma < NOISE_SIGMA_THRESHOLD
    assert high_metrics.noise_sigma < NOISE_SIGMA_THRESHOLD


def test_enhance_page_image_skips_clahe_and_denoise_on_already_clean_page(monkeypatch):
    import app.services.image_enhancement as mod

    clahe_calls = []
    denoise_calls = []

    original_create_clahe = mod.cv2.createCLAHE
    original_denoise = mod.cv2.fastNlMeansDenoisingColored

    def spy_create_clahe(*args, **kwargs):
        clahe_calls.append((args, kwargs))
        return original_create_clahe(*args, **kwargs)

    def spy_denoise(*args, **kwargs):
        denoise_calls.append((args, kwargs))
        return original_denoise(*args, **kwargs)

    monkeypatch.setattr(mod.cv2, "createCLAHE", spy_create_clahe)
    monkeypatch.setattr(mod.cv2, "fastNlMeansDenoisingColored", spy_denoise)

    enhance_page_image(_make_high_contrast_sharp_page_png())

    assert clahe_calls == []
    assert denoise_calls == []


def test_enhance_page_image_applies_clahe_on_low_contrast_page(monkeypatch):
    import app.services.image_enhancement as mod

    clahe_calls = []
    original_create_clahe = mod.cv2.createCLAHE

    def spy_create_clahe(*args, **kwargs):
        clahe_calls.append((args, kwargs))
        return original_create_clahe(*args, **kwargs)

    monkeypatch.setattr(mod.cv2, "createCLAHE", spy_create_clahe)

    enhance_page_image(_make_low_contrast_page_png())

    assert len(clahe_calls) == 1


def _make_noisy_page_png() -> bytes:
    """A page with real per-pixel random noise added — should read above
    NOISE_SIGMA_THRESHOLD and actually trigger denoising, unlike the other
    synthetic fixtures above (which are noise-free by construction)."""
    import cv2

    img = Image.new("L", (800, 1000), color=255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()
    for i in range(15):
        draw.text((60, 60 + i * 50), f"Sale deed line {i} — property record text", fill=0, font=font)

    arr = np.array(img).astype(np.int16)
    rng = np.random.default_rng(seed=42)
    arr = np.clip(arr + rng.normal(0, 20, arr.shape), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def test_enhance_page_image_applies_denoise_on_noisy_page(monkeypatch):
    import app.services.image_enhancement as mod

    denoise_calls = []
    original_denoise = mod.cv2.fastNlMeansDenoisingColored

    def spy_denoise(*args, **kwargs):
        denoise_calls.append((args, kwargs))
        return original_denoise(*args, **kwargs)

    monkeypatch.setattr(mod.cv2, "fastNlMeansDenoisingColored", spy_denoise)

    enhance_page_image(_make_noisy_page_png())

    assert len(denoise_calls) == 1


def test_enhance_page_image_preserves_color():
    # A colored (red) stamp-like rectangle on an otherwise plain page —
    # the whole point of the color-preservation change is that a signal
    # like this survives cleaning instead of being discarded via an
    # upfront grayscale conversion.
    img = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((550, 850, 700, 920), fill=(200, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    enhanced = enhance_page_image(buf.getvalue())
    enh_arr = np.array(Image.open(io.BytesIO(enhanced)).convert("RGB"))

    # Sample the stamp region: a grayscale-collapsed image would have
    # R == G == B everywhere; a color-preserved one keeps the red channel
    # meaningfully higher than green/blue there.
    region = enh_arr[860:910, 560:690]
    assert region[:, :, 0].mean() > region[:, :, 1].mean() + 30
    assert region[:, :, 0].mean() > region[:, :, 2].mean() + 30
