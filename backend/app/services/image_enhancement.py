"""
Page image enhancement — runs on every rasterized page image before it goes
to either the OCR engine or the VLM (see app/services/document_router.py),
so both extraction paths read the cleanest version of the page rather than
a raw scan/rasterization.

Color is preserved end to end — earlier versions of this module converted to
grayscale up front, on the reasoning that neither OCR nor the VLM needed
color. That held for OCR (tesseract_provider.py converts to RGB internally
regardless of what it's handed, so it never cared either way), but not for
the VLM: a colored stamp, red ink correction, or highlighted clause is a real
signal Gemini can read and grayscale was throwing away before it ever got
the chance. Cleaning now happens on the color image directly — CLAHE runs on
just the L channel of a LAB conversion (contrast correction without shifting
color balance) and denoising uses OpenCV's colored variant — with all
*measurement* (blur/contrast/noise/skew, below) still done on a throwaway
grayscale conversion, since those metrics only need luminance.

Every step past that is decided by a quick quality assessment of the
*original* page (blur, contrast, noise, skew) rather than applied
unconditionally — a crisp rasterization of a born-digital PDF should pass
through close to untouched, while a noisy, low-contrast, tilted phone-scan
needs the full treatment. Running the full fixed pipeline on every page
regardless of its actual condition wastes time on already-clean pages and
risks over-processing them: denoising a page that was never noisy just
softens fine text edges, and sharpening a page that's already crisp mostly
adds ringing around edges — neither helps OCR/VLM read it, and both can hurt.

Steps that do run stay ordered so each operates on a reasonably clean input
from the step before it (deskew before denoise, since a skewed page confuses
noise removal's neighborhood assumptions; denoise before contrast, since
CLAHE would otherwise amplify noise; sharpen last, since sharpening before
denoising would sharpen the noise too).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Tuple

import cv2
import numpy as np


# Cap on absolute rotation correction — a "deskew" past this is more likely a
# false read of a mostly-blank or non-text page than an actual skewed scan,
# so leave the image alone rather than rotating it based on noise.
MAX_DESKEW_ANGLE_DEGREES = 15.0

# CLAHE (contrast-limited adaptive histogram equalization) tile grid + clip.
CLAHE_CLIP_LIMIT = 2.0
CLAHE_STRONG_CLIP_LIMIT = 3.5
CLAHE_TILE_GRID_SIZE = (8, 8)

# --- Quality thresholds that decide which steps below actually run --------

# Variance of the Laplacian — a standard cheap blur proxy (lots of
# high-frequency edge content = sharp; a flat, blurry page has little).
# Below this, the page is blurry enough that sharpening is worth the risk of
# also amplifying whatever noise is left; at or above it, the page is
# already crisp and sharpening would mostly add ringing rather than help.
SHARPNESS_VARIANCE_THRESHOLD = 150.0

# Standard deviation of pixel intensity. Below this the page is genuinely
# low-contrast (a faint carbon copy, a washed-out scan) and benefits from
# CLAHE; below the stricter threshold it's severe enough to warrant a
# stronger clip limit. At or above the low threshold there's already enough
# separation between ink and background that CLAHE would mostly stretch
# noise rather than improve legibility.
CONTRAST_STD_LOW_THRESHOLD = 45.0
CONTRAST_STD_VERY_LOW_THRESHOLD = 25.0

# Estimated Gaussian noise sigma (Immerkaer 1996 fast estimator, see
# _estimate_noise_sigma). Most rasterized/born-digital PDF pages come out
# near 0; real noise from a phone camera or a low-quality scanner typically
# reads several times higher. Below this, denoising is skipped — it only
# softens fine text edges on a page that was never actually noisy.
NOISE_SIGMA_THRESHOLD = 3.0


@dataclass
class PageQualityMetrics:
    sharpness: float  # Laplacian variance; higher = sharper
    contrast: float  # pixel-intensity std; higher = more contrast
    noise_sigma: float  # estimated Gaussian noise std; higher = noisier
    skew_angle: float  # degrees needed to make text horizontal


def _decode_png(png_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image bytes as PNG")
    return image


def _encode_png(image: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Could not encode enhanced image as PNG")
    return buf.tobytes()


def _estimate_skew_angle(gray: np.ndarray) -> float:
    """Estimates rotation (in degrees) needed to make text horizontal, using
    the minimum-area bounding rectangle of thresholded ink pixels. Returns 0.0
    on a blank/near-blank page rather than raising, since not every page has
    enough text mass to estimate an angle from."""
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(thresh)
    if coords is None or len(coords) < 50:
        return 0.0

    angle = cv2.minAreaRect(coords)[-1]
    # cv2.minAreaRect returns an angle in [-90, 0); normalize to a signed
    # rotation close to 0 (i.e. "nearly upright, tilted slightly one way").
    if angle < -45:
        angle = 90 + angle
    return -angle


def _estimate_noise_sigma(gray: np.ndarray) -> float:
    """Fast Gaussian noise estimate (Immerkaer, 1996): convolves with a
    kernel that cancels out smooth gradients/edges but responds to
    isolated pixel-level noise, then scales the mean absolute response to
    approximate the noise's standard deviation. Cheap enough to run on every
    page before deciding whether denoising is actually worth doing."""
    h, w = gray.shape[:2]
    if h < 3 or w < 3:
        return 0.0

    kernel = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float64)
    response = cv2.filter2D(gray.astype(np.float64), -1, kernel)
    sigma = np.sum(np.abs(response)) * math.sqrt(0.5 * math.pi) / (6 * (w - 2) * (h - 2))
    return float(sigma)


def _assess_quality(gray: np.ndarray) -> PageQualityMetrics:
    """Measures the *original* page once, before any cleaning step has
    touched it — later steps decide what to do based on these numbers rather
    than each other's output, so e.g. a denoise pass doesn't make the page
    look artificially sharp enough to skip sharpening it actually needs."""
    return PageQualityMetrics(
        sharpness=float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        contrast=float(gray.std()),
        noise_sigma=_estimate_noise_sigma(gray),
        skew_angle=_estimate_skew_angle(gray),
    )


def _rotate_to_correct_skew(image: np.ndarray, angle: float) -> np.ndarray:
    """Applies the rotation correction for a skew angle already measured by
    _assess_quality. Takes the angle as a parameter (rather than
    re-measuring it) so the same estimate used for the quality report is the
    one actually corrected for. Works on grayscale or color alike —
    cv2.warpAffine doesn't care how many channels `image` has."""
    if abs(angle) < 0.1 or abs(angle) > MAX_DESKEW_ANGLE_DEGREES:
        return image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    # Correcting a detected tilt of `angle` degrees means rotating the image
    # by the opposite amount — passing `angle` straight through compounds the
    # skew instead of undoing it (verified empirically: an 8deg-tilted test
    # page measured ~16deg after "deskewing" with the un-negated angle).
    matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
    )


def _sharpen(image: np.ndarray) -> np.ndarray:
    """Unsharp mask: subtract a blurred copy from the original to emphasize
    edges, rather than a fixed convolution kernel — scales better across the
    range of page resolutions RASTER_DPI can produce. Works on grayscale or
    color alike — GaussianBlur/addWeighted apply per-channel automatically."""
    blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=3)
    return cv2.addWeighted(image, 1.5, blurred, -0.5, 0)


def _denoise_color(image: np.ndarray) -> np.ndarray:
    """Colored counterpart to cv2.fastNlMeansDenoising — denoises luminance
    and color channels separately (hColor mirrors h) instead of collapsing
    to grayscale first, which is what let color survive to the VLM in the
    first place."""
    return cv2.fastNlMeansDenoisingColored(
        image, None, h=10, hColor=10, templateWindowSize=7, searchWindowSize=21,
    )


def _apply_clahe_to_lightness(image: np.ndarray, clip: float) -> np.ndarray:
    """Contrast correction that preserves color: CLAHE only makes sense on a
    single-channel image, so this runs it on the L (lightness) channel of a
    LAB conversion and merges back, rather than on the color channels
    directly — stretching contrast without shifting hue/saturation the way
    equalizing each of R/G/B independently would."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=CLAHE_TILE_GRID_SIZE)
    l_channel = clahe.apply(l_channel)
    lab = cv2.merge((l_channel, a_channel, b_channel))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def enhance_page_image_with_report(png_bytes: bytes) -> Tuple[bytes, Dict[str, Any]]:
    """Same cleaning pipeline as enhance_page_image, but also returns a
    report of what the quality assessment measured and which steps actually
    ran. enhance_page_image itself (below) is a thin wrapper around this that
    only returns the bytes — this is the version pipeline_service.py calls,
    so it can log per page, per document, whether/why a page went through
    denoise/contrast/sharpen (this module has no document_id/page_number of
    its own to log against).

    report is one of:
      {"fallback": True} — decode/processing failed, png_bytes returned as-is
      {"sharpness": float, "contrast": float, "noise_sigma": float,
       "skew_angle": float, "deskewed": bool, "denoised": bool,
       "clahe_applied": bool, "clahe_clip": float | None, "sharpened": bool}
    """
    try:
        image = _decode_png(png_bytes)
        # Grayscale exists only to measure the page — the actual working
        # buffer stays `image` (color) all the way through, so whatever
        # steps end up running below act on the color original, not a
        # desaturated copy of it.
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        metrics = _assess_quality(gray)
        report: Dict[str, Any] = {
            "sharpness": round(metrics.sharpness, 1),
            "contrast": round(metrics.contrast, 1),
            "noise_sigma": round(metrics.noise_sigma, 2),
            "skew_angle": round(metrics.skew_angle, 2),
            "deskewed": 0.1 <= abs(metrics.skew_angle) <= MAX_DESKEW_ANGLE_DEGREES,
            "denoised": False,
            "clahe_applied": False,
            "clahe_clip": None,
            "sharpened": False,
            "fallback": False,
        }

        image = _rotate_to_correct_skew(image, metrics.skew_angle)

        if metrics.noise_sigma > NOISE_SIGMA_THRESHOLD:
            image = _denoise_color(image)
            report["denoised"] = True

        if metrics.contrast < CONTRAST_STD_LOW_THRESHOLD:
            clip = (
                CLAHE_STRONG_CLIP_LIMIT
                if metrics.contrast < CONTRAST_STD_VERY_LOW_THRESHOLD
                else CLAHE_CLIP_LIMIT
            )
            image = _apply_clahe_to_lightness(image, clip)
            report["clahe_applied"] = True
            report["clahe_clip"] = clip

        if metrics.sharpness < SHARPNESS_VARIANCE_THRESHOLD:
            image = _sharpen(image)
            report["sharpened"] = True

        return _encode_png(image), report
    except Exception:
        return png_bytes, {"fallback": True}


def enhance_page_image(png_bytes: bytes) -> bytes:
    """Takes a rasterized page (PNG bytes, as produced by PyMuPDF's
    pixmap.tobytes("png") or a normalized upload), returns enhanced PNG
    bytes in color: deskewed/denoised/contrast-enhanced/sharpened as the
    page's own measured quality calls for (see module docstring and
    PageQualityMetrics — not every page gets every step).

    On any failure, returns the original bytes unchanged rather than raising —
    a page that can't be enhanced should still go through OCR/VLM as-is,
    not block the pipeline. See enhance_page_image_with_report for a version
    that also reports what it did/measured.
    """
    return enhance_page_image_with_report(png_bytes)[0]
