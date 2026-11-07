from pathlib import Path
import re
import cv2
import numpy as np

PLATE_PATTERN = re.compile(
    r"^(?:[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4})$"
)

def _phash(gray: np.ndarray) -> str:
    resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))
    low = dct[:8, :8]
    values = low.flatten()[1:]
    median = np.median(values)
    bits = values > median
    return "".join("1" if bit else "0" for bit in bits)

def analyze_image(path: str) -> dict:
    image = cv2.imread(str(Path(path)))
    if image is None:
        raise ValueError("OpenCV could not decode the stored image")

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    phash = _phash(gray)

    checks = {
        "dimensions": {
            "passed": width >= 300 and height >= 300,
            "width": int(width),
            "height": int(height),
            "message": "Minimum dimension threshold is 300x300 pixels.",
        },
        "blur": {
            "passed": blur_score >= 100.0,
            "score": round(blur_score, 2),
            "message": "Laplacian variance; low values may indicate blur. Threshold is heuristic.",
        },
        "brightness": {
            "passed": 35.0 <= brightness <= 220.0,
            "mean_grayscale": round(brightness, 2),
            "message": "Mean grayscale brightness; values outside 35–220 may indicate poor lighting.",
        },
        "duplicate_fingerprint": {
            "passed": True,
            "phash": phash,
            "message": "Perceptual fingerprint used for near-duplicate comparison against prior completed uploads.",
        },
        "ocr": {
            "passed": False,
            "text": None,
            "message": "OCR is not configured in this starter. Add Tesseract/EasyOCR to enable extraction.",
        },
        "number_plate_format": {
            "passed": False,
            "normalized_text": None,
            "message": "Cannot validate plate format until OCR text is available.",
            "pattern": "Indian private vehicle format heuristic: AA12AA1234 (variants exist).",
        },
    }

    failed_checks = [name for name, result in checks.items() if not result["passed"]]
    passed_count = sum(1 for result in checks.values() if result["passed"])
    confidence = round(passed_count / len(checks), 2)

    return {
        "checks": checks,
        "summary": {
            "checks_passed": passed_count,
            "checks_total": len(checks),
            "flagged_checks": failed_checks,
            "confidence_score": confidence,
            "confidence_note": "This is a rule-based screening score, not a probability of fraud or authenticity.",
        },
        "limitations": [
            "Blur and brightness thresholds are heuristics and should be calibrated on representative data.",
            "A perceptual hash is generated but duplicate lookup is not yet persisted across uploads.",
            "OCR and plate validation require an OCR engine and should not be treated as definitive legal validation.",
            "This pipeline does not prove whether an image is edited, a screenshot, or a photo of a photo.",
        ],
    }
