"""OpenCV computer vision quality checks and PDF image/text extraction."""

import io
from dataclasses import dataclass

import cv2
import numpy as np
from pypdf import PdfReader


@dataclass(frozen=True)
class ImageQualityMetrics:
    quality_status: str
    blur_score: float | None
    glare_ratio: float | None
    edge_clip_ratio: float | None
    face_detected: bool | None
    width: int | None
    height: int | None


def extract_pdf_payload(data: bytes) -> tuple[str, list[bytes]]:
    """Extract embedded text and raster images from a PDF document."""
    try:
        reader = PdfReader(io.BytesIO(data))
        texts: list[str] = []
        images: list[bytes] = []
        for page in reader.pages:
            page_text = (page.extract_text() or "").strip()
            if page_text:
                texts.append(page_text)
            for img_file in getattr(page, "images", []) or []:
                if getattr(img_file, "data", None):
                    images.append(img_file.data)
        return "\n".join(texts).strip(), images
    except Exception:  # noqa: BLE001
        return "", []


def decode_image(image_bytes: bytes) -> np.ndarray | None:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    if arr.size == 0:
        return None
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _detect_face(gray: np.ndarray) -> bool:
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    if cascade.empty():
        return False
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
    return len(faces) > 0


def analyze_image_quality(image_bytes: bytes, *, check_face: bool = False) -> ImageQualityMetrics:
    """Measure Laplacian blur variance, localized glare, border edge clipping, and face presence."""
    img = decode_image(image_bytes)
    if img is None:
        return ImageQualityMetrics(
            quality_status="UNREADABLE",
            blur_score=None,
            glare_ratio=None,
            edge_clip_ratio=None,
            face_detected=False if check_face else None,
            width=None,
            height=None,
        )

    height, width = img.shape[:2]
    if width < 220 or height < 140:
        return ImageQualityMetrics(
            quality_status="LOW_RESOLUTION",
            blur_score=0.0,
            glare_ratio=0.0,
            edge_clip_ratio=0.0,
            face_detected=False if check_face else None,
            width=width,
            height=height,
        )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Detect genuine specular glare hotspots (blown-out 253+ white patch on a darker card,
    # while avoiding false positives on clean white-paper synthetic documents).
    bright_mask = gray >= 253
    glare_ratio = float(np.mean(bright_mask))
    dark_ratio = float(np.mean(gray < 210))
    glare_flag = 0.16 <= glare_ratio <= 0.65 and dark_ratio >= 0.15 and blur_score < 220.0

    # Check border edge energy for cropped/clipped edges
    edges = cv2.Canny(gray, 80, 180) > 0
    border = 3
    top_edge = float(np.mean(edges[:border, :]))
    bottom_edge = float(np.mean(edges[-border:, :]))
    left_edge = float(np.mean(edges[:, :border]))
    right_edge = float(np.mean(edges[:, -border:]))
    clipped_sides = sum(1 for r in (top_edge, bottom_edge, left_edge, right_edge) if r > 0.25)
    edge_clip_ratio = max(top_edge, bottom_edge, left_edge, right_edge)

    face_detected: bool | None = _detect_face(gray) if check_face else None

    if check_face and not face_detected:
        status = "FACE_NOT_DETECTED"
    elif blur_score < 45.0:
        status = "IMAGE_BLURRY"
    elif glare_flag:
        status = "IMAGE_GLARE"
    elif clipped_sides >= 3 and edge_clip_ratio > 0.35:
        status = "IMAGE_CROPPED"
    else:
        status = "OK"

    return ImageQualityMetrics(
        quality_status=status,
        blur_score=round(blur_score, 2),
        glare_ratio=round(glare_ratio, 4),
        edge_clip_ratio=round(edge_clip_ratio, 4),
        face_detected=face_detected,
        width=width,
        height=height,
    )
