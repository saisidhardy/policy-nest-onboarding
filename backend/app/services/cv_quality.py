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


def _load_image_from_payload(raw_bytes: bytes, content_type: str) -> np.ndarray | None:
    """Decode image bytes or extract the primary raster image from a PDF wrapper."""
    if content_type == "application/pdf":
        _, pdf_images = extract_pdf_payload(raw_bytes)
        best: np.ndarray | None = None
        best_area = 0
        for candidate in pdf_images:
            img = decode_image(candidate)
            if img is not None:
                area = img.shape[0] * img.shape[1]
                if area > best_area:
                    best = img
                    best_area = area
        return best
    return decode_image(raw_bytes)


def _detect_faces(
    gray: np.ndarray,
    *,
    min_size: int = 40,
    upscale_min_width: int = 0,
) -> list[tuple[int, int, int, int]]:
    """Detect frontal faces using alt2 cascade with default cascade fallback."""
    h, w = gray.shape[:2]
    scale = 1.0
    work = gray
    if upscale_min_width > 0 and 0 < w < upscale_min_width:
        scale = upscale_min_width / float(w)
        work = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    for cascade_file in ("haarcascade_frontalface_alt2.xml", "haarcascade_frontalface_default.xml"):
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + cascade_file)
        if cascade.empty():
            continue
        faces = cascade.detectMultiScale(
            work,
            scaleFactor=1.08,
            minNeighbors=4 if cascade_file.endswith("default.xml") else 3,
            minSize=(min_size, min_size),
        )
        if len(faces) > 0:
            boxes = [
                (int(x / scale), int(y / scale), int(fw / scale), int(fh / scale))
                for (x, y, fw, fh) in faces
            ]
            boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
            return boxes
    return []


def _detect_face(gray: np.ndarray) -> bool:
    return len(_detect_faces(gray, min_size=40)) > 0


def _compare_face_crops(img_a: np.ndarray, box_a: tuple[int, int, int, int], img_b: np.ndarray, box_b: tuple[int, int, int, int]) -> float:
    """Compute a bounded [0, 1] local OpenCV visual similarity score between two cropped face regions."""
    def _prep(img: np.ndarray, box: tuple[int, int, int, int]) -> tuple[np.ndarray, np.ndarray]:
        x, y, w, h = box
        ih, iw = img.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(iw, x + w), min(ih, y + h)
        roi = cv2.resize(img[y0:y1, x0:x1], (96, 96), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(gray)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        return clahe, hist

    gray_a, hist_a = _prep(img_a, box_a)
    gray_b, hist_b = _prep(img_b, box_b)

    # Inner portrait mask emphasizes eyes/nose/mouth region over background collar/frame
    inner_a = gray_a[16:80, 16:80].astype(np.float32).ravel()
    inner_b = gray_b[16:80, 16:80].astype(np.float32).ravel()
    inner_a -= inner_a.mean()
    inner_b -= inner_b.mean()
    denom = float(np.linalg.norm(inner_a) * np.linalg.norm(inner_b))
    struct_sim = max(0.0, float(np.dot(inner_a, inner_b) / denom)) if denom > 1e-6 else 0.0

    hist_corr = max(0.0, float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)))
    combined = 0.65 * struct_sim + 0.35 * hist_corr
    return round(max(0.0, min(1.0, combined)), 3)


def compare_selfie_to_id_opencv(
    *,
    selfie_bytes: bytes | None,
    selfie_mime: str | None,
    aadhaar_bytes: bytes | None = None,
    aadhaar_mime: str | None = None,
    pan_bytes: bytes | None = None,
    pan_mime: str | None = None,
) -> dict[str, object]:
    """Compare applicant selfie face against ID card portraits using OpenCV (non-biometric local screening)."""
    selfie_img = _load_image_from_payload(selfie_bytes, selfie_mime) if selfie_bytes and selfie_mime else None
    selfie_boxes: list[tuple[int, int, int, int]] = []
    if selfie_img is not None:
        selfie_boxes = _detect_faces(cv2.cvtColor(selfie_img, cv2.COLOR_BGR2GRAY), min_size=40)

    result: dict[str, object] = {
        "selfie_face_detected": bool(selfie_boxes),
        "selfie_face_count": len(selfie_boxes),
        "aadhaar_face_detected": False,
        "aadhaar_cv_similarity": None,
        "pan_face_detected": False,
        "pan_cv_similarity": None,
        "overall_cv_similarity": None,
    }

    scores: list[float] = []
    for key_prefix, payload, mime in (
        ("aadhaar", aadhaar_bytes, aadhaar_mime),
        ("pan", pan_bytes, pan_mime),
    ):
        if not payload or not mime:
            continue
        id_img = _load_image_from_payload(payload, mime)
        if id_img is None:
            continue
        boxes = _detect_faces(
            cv2.cvtColor(id_img, cv2.COLOR_BGR2GRAY),
            min_size=28,
            upscale_min_width=1200,
        )
        result[f"{key_prefix}_face_detected"] = bool(boxes)
        if boxes and selfie_img is not None and selfie_boxes:
            sim = _compare_face_crops(selfie_img, selfie_boxes[0], id_img, boxes[0])
            result[f"{key_prefix}_cv_similarity"] = sim
            scores.append(sim)

    if scores:
        result["overall_cv_similarity"] = round(max(scores), 3)
    return result


def analyze_image_quality(
    image_bytes: bytes,
    *,
    check_face: bool = False,
    detect_face: bool = False,
) -> ImageQualityMetrics:
    """Measure Laplacian blur variance, localized glare, border edge clipping, and face presence."""
    want_face = check_face or detect_face
    img = decode_image(image_bytes)
    if img is None:
        return ImageQualityMetrics(
            quality_status="UNREADABLE",
            blur_score=None,
            glare_ratio=None,
            edge_clip_ratio=None,
            face_detected=False if want_face else None,
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
            face_detected=False if want_face else None,
            width=width,
            height=height,
        )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if float(np.std(gray)) < 4.5:
        return ImageQualityMetrics(
            quality_status="UNREADABLE",
            blur_score=0.0,
            glare_ratio=0.0,
            edge_clip_ratio=0.0,
            face_detected=False if want_face else None,
            width=width,
            height=height,
        )
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

    face_detected: bool | None = _detect_face(gray) if want_face else None

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
