from pathlib import Path
import re
from functools import lru_cache

import cv2
import numpy as np

from app.config import settings


INDIAN_STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CH", "CG", "DD", "DL",
    "DN", "GA", "GJ", "HP", "HR", "JH", "JK", "KA", "KL",
    "LA", "LD", "MH", "ML", "MN", "MP", "MZ", "NL", "OD",
    "PB", "PY", "RJ", "SK", "TN", "TR", "TS", "UK", "UP",
    "WB",
}

STANDARD_PLATE_PATTERN = re.compile(
    r"([A-Z]{2})([0-9]{1,2})([A-Z]{1,3})([0-9]{4})"
)

BH_PLATE_PATTERN = re.compile(
    r"([0-9]{2})BH([0-9]{4})([A-Z]{2})"
)

LETTER_TO_DIGIT = {
    "O": "0", "Q": "0", "I": "1", "L": "1",
    "Z": "2", "S": "5", "G": "6", "B": "8",
}

DIGIT_TO_LETTER = {
    "0": "O", "1": "I", "2": "Z",
    "5": "S", "6": "G", "8": "B",
}


def _phash(image, hash_size=8, highfreq_factor=4):
    """Generate a perceptual hash for duplicate comparison."""
    size = hash_size * highfreq_factor

    resized = cv2.resize(
        image,
        (size, size),
        interpolation=cv2.INTER_AREA,
    )

    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    dct = cv2.dct(np.float32(gray))
    low_freq = dct[:hash_size, :hash_size]

    median = np.median(low_freq[1:, 1:])
    diff = low_freq > median

    return "".join(
        "1" if value else "0"
        for value in diff.flatten()
    )


@lru_cache(maxsize=1)
def _get_ocr_engine():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def _run_ocr(image):
    """Run RapidOCR and return text lines with confidence."""
    engine = _get_ocr_engine()
    result, _ = engine(image)

    lines = []

    for item in result or []:
        if not item or len(item) < 3:
            continue

        text = str(item[1]).strip()

        if not text:
            continue

        try:
            confidence = float(item[2])
        except (TypeError, ValueError):
            confidence = 0.0

        lines.append({
            "text": text,
            "confidence": max(0.0, min(confidence, 1.0)),
        })

    return lines


def _extract_text(image):
    """Extract text from the complete image."""
    try:
        lines = _run_ocr(image)

        average_confidence = (
            sum(line["confidence"] for line in lines) / len(lines)
            if lines else 0.0
        )

        return {
            "status": "completed",
            "lines": lines,
            "text": "\n".join(line["text"] for line in lines),
            "confidence": round(average_confidence, 4),
        }

    except Exception as exc:
        return {
            "status": "skipped",
            "lines": [],
            "text": "",
            "confidence": 0.0,
            "error": str(exc)[:300],
        }


def _preprocess_plate_crop(crop):
    """Return independent CLAHE and adaptive-threshold OCR variants."""
    height, width = crop.shape[:2]

    if height == 0 or width == 0:
        return {}

    variants = {}

    # v2.2 path: stronger enlargement + CLAHE.
    scale_clahe = min(4.0, max(2.0, 1200 / max(width, height)))

    enlarged_clahe = cv2.resize(
        crop,
        (
            max(1, int(width * scale_clahe)),
            max(1, int(height * scale_clahe)),
        ),
        interpolation=cv2.INTER_CUBIC,
    )

    gray_clahe = cv2.cvtColor(
        enlarged_clahe,
        cv2.COLOR_BGR2GRAY,
    )

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    enhanced = clahe.apply(gray_clahe)

    variants["clahe"] = cv2.cvtColor(
        enhanced,
        cv2.COLOR_GRAY2BGR,
    )

    # v2.1 path: preserve adaptive-threshold preprocessing.
    scale_adaptive = min(
        3.0,
        max(1.5, 1000 / max(width, height)),
    )

    enlarged_adaptive = cv2.resize(
        crop,
        (
            max(1, int(width * scale_adaptive)),
            max(1, int(height * scale_adaptive)),
        ),
        interpolation=cv2.INTER_CUBIC,
    )

    gray_adaptive = cv2.cvtColor(
        enlarged_adaptive,
        cv2.COLOR_BGR2GRAY,
    )

    adaptive_clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    adaptive_enhanced = adaptive_clahe.apply(gray_adaptive)

    thresholded = cv2.adaptiveThreshold(
        adaptive_enhanced,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    variants["adaptive_threshold"] = cv2.cvtColor(
        thresholded,
        cv2.COLOR_GRAY2BGR,
    )

    return variants


def _get_fixed_plate_regions(image):
    """Existing overlapping candidate regions."""
    height, width = image.shape[:2]

    region_specs = [
        ("bottom_full", 0.00, 0.48, 1.00, 1.00),
        ("bottom_center", 0.10, 0.55, 0.90, 1.00),
        ("bottom_right", 0.35, 0.52, 1.00, 1.00),
        ("bottom_left", 0.00, 0.52, 0.70, 1.00),
        ("center_lower", 0.10, 0.35, 0.95, 0.90),
        ("center", 0.10, 0.20, 0.90, 0.80),
    ]

    regions = []

    for name, x1, y1, x2, y2 in region_specs:
        left = int(width * x1)
        top = int(height * y1)
        right = int(width * x2)
        bottom = int(height * y2)

        crop = image[top:bottom, left:right]

        if crop.size:
            regions.append((name, crop))

    return regions


def _detect_yellow_plate_regions(image):
    """
    Detect potential yellow registration plate regions.

    This is a heuristic proposal generator, not a trained
    number-plate detector. OCR and format validation follow it.
    """
    height, width = image.shape[:2]

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    lower_yellow = np.array([15, 65, 65], dtype=np.uint8)
    upper_yellow = np.array([40, 255, 255], dtype=np.uint8)

    mask = cv2.inRange(
        hsv,
        lower_yellow,
        upper_yellow,
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (5, 5),
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=2,
    )

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    proposals = []
    image_area = width * height

    for contour in contours:
        area = cv2.contourArea(contour)

        if area < max(250, image_area * 0.0002):
            continue

        if area > image_area * 0.08:
            continue

        x, y, w, h = cv2.boundingRect(contour)

        if w < 30 or h < 18:
            continue

        aspect_ratio = w / float(h)

        if not 0.75 <= aspect_ratio <= 6.5:
            continue

        if y < int(height * 0.35):
            continue

        pad_x = max(8, int(w * 0.18))
        pad_y = max(8, int(h * 0.25))

        left = max(0, x - pad_x)
        top = max(0, y - pad_y)
        right = min(width, x + w + pad_x)
        bottom = min(height, y + h + pad_y)

        crop = image[top:bottom, left:right]

        if crop.size == 0:
            continue

        proposals.append({
            "box": (left, top, right, bottom),
            "crop": crop,
            "area": area,
        })

    proposals.sort(
        key=lambda item: item["area"]
    )

    return proposals[:12]


def _boxes_overlap(box_a, box_b):
    """Calculate intersection-over-union for two boxes."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)

    union = area_a + area_b - intersection

    return intersection / union if union else 0.0


def _get_plate_regions(image):
    """Combine fixed crops with adaptive yellow-region proposals."""
    regions = _get_fixed_plate_regions(image)

    proposals = _detect_yellow_plate_regions(image)
    accepted_boxes = []

    for index, proposal in enumerate(proposals):
        box = proposal["box"]

        if any(
            _boxes_overlap(box, previous) > 0.75
            for previous in accepted_boxes
        ):
            continue

        accepted_boxes.append(box)

        regions.append((
            f"yellow_candidate_{index + 1}",
            proposal["crop"],
        ))

    return regions


def _extract_plate_region_text(image):
    """OCR every fixed/yellow crop with both preprocessing strategies."""
    results = []

    for region_name, crop in _get_plate_regions(image):
        try:
            processed_variants = _preprocess_plate_crop(crop)

            for preprocessing_name, processed in processed_variants.items():
                try:
                    lines = _run_ocr(processed)

                    if lines:
                        results.append({
                            "region": region_name,
                            "preprocessing": preprocessing_name,
                            "lines": lines,
                        })

                except Exception:
                    continue

        except Exception:
            continue

    return results


def _normalize_ocr_text(text):
    return re.sub(r"[^A-Z0-9]", "", str(text).upper())


def _generate_plate_variants(text):
    """Generate conservative one-character OCR alternatives."""
    variants = {text}

    for index, char in enumerate(text):
        replacement = LETTER_TO_DIGIT.get(char)

        if replacement:
            variants.add(
                text[:index] + replacement + text[index + 1:]
            )

        replacement = DIGIT_TO_LETTER.get(char)

        if replacement:
            variants.add(
                text[:index] + replacement + text[index + 1:]
            )

    return variants


def _validate_plate_candidate(candidate):
    """Validate standard Indian and Bharat series formats."""
    standard_match = STANDARD_PLATE_PATTERN.fullmatch(candidate)

    if standard_match:
        state_code, district_code, series, number = (
            standard_match.groups()
        )

        if state_code not in INDIAN_STATE_CODES:
            return None

        district = int(district_code)

        if district < 1 or district > 99:
            return None

        return {
            "plate": candidate,
            "series": "standard",
            "state_code": state_code,
            "district_code": district_code,
            "format_valid": True,
            "reason": "Recognized Indian state/UT prefix.",
        }

    bh_match = BH_PLATE_PATTERN.fullmatch(candidate)

    if bh_match:
        year, number, suffix = bh_match.groups()

        if 21 <= int(year) <= 99:
            return {
                "plate": candidate,
                "series": "bharat",
                "state_code": None,
                "district_code": None,
                "format_valid": True,
                "reason": "Recognized Bharat series format.",
            }

    return None


def _detect_number_plates(lines):
    """Detect possible plate candidates across adjacent OCR lines."""
    candidates = []
    seen = set()

    for start in range(len(lines)):
        combined = ""

        for end in range(start, min(start + 3, len(lines))):
            combined += _normalize_ocr_text(lines[end]["text"])

            if len(combined) < 8 or len(combined) > 16:
                continue

            for variant in _generate_plate_variants(combined):
                validated = _validate_plate_candidate(variant)

                if not validated:
                    continue

                key = (validated["plate"], start, end)

                if key in seen:
                    continue

                seen.add(key)

                direct_match = variant == combined

                source_confidence = min(
                    lines[index]["confidence"]
                    for index in range(start, end + 1)
                )

                candidate_confidence = (
                    source_confidence
                    if direct_match
                    else source_confidence * 0.75
                )

                candidates.append({
                    **validated,
                    "ocr_confidence": round(source_confidence, 4),
                    "direct_ocr_match": direct_match,
                    "source_lines": list(range(start, end + 1)),
                    "candidate_confidence": round(
                        candidate_confidence,
                        4,
                    ),
                })

    candidates.sort(
        key=lambda item: item["candidate_confidence"],
        reverse=True,
    )

    return candidates


def _check(status, message, **metrics):
    return {
        "status": status,
        "passed": (
            True if status == "pass"
            else False if status == "fail"
            else None
        ),
        "message": message,
        **metrics,
    }


def _build_summary(checks):
    statuses = [
        check["status"]
        for check in checks.values()
    ]

    passed = statuses.count("pass")
    failed = statuses.count("fail")
    skipped = statuses.count("skipped")
    unknown = statuses.count("unknown")

    evaluated = passed + failed
    total = len(statuses)

    return {
        "checks_passed": passed,
        "checks_failed": failed,
        "checks_skipped": skipped,
        "checks_unknown": unknown,
        "total_checks": total,
        "evaluated_checks": evaluated,
        "confidence": round(passed / evaluated, 4) if evaluated else 0.0,
        "flagged_checks": [
            name for name, check in checks.items()
            if check["status"] == "fail"
        ],
        "skipped_checks": [
            name for name, check in checks.items()
            if check["status"] == "skipped"
        ],
        "unknown_checks": [
            name for name, check in checks.items()
            if check["status"] == "unknown"
        ],
    }


def analyze_image(path):
    """Run image quality, OCR, plate-region and fingerprint analysis."""
    path = Path(path)

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Unable to decode image.")

    height, width = image.shape[:2]
    original_pixels = width * height

    if original_pixels > settings.max_image_pixels:
        raise ValueError("Image exceeds maximum allowed pixel count.")

    # Keep original resolution for plate-region OCR.
    plate_search_image = image

    # Downscale main analysis image if required.
    analysis_image = image.copy()
    max_edge = settings.analysis_max_edge

    if max(width, height) > max_edge:
        scale = max_edge / max(width, height)

        analysis_image = cv2.resize(
            image,
            (
                max(1, int(width * scale)),
                max(1, int(height * scale)),
            ),
            interpolation=cv2.INTER_AREA,
        )

    gray = cv2.cvtColor(
        analysis_image,
        cv2.COLOR_BGR2GRAY,
    )

    blur_score = float(
        cv2.Laplacian(gray, cv2.CV_64F).var()
    )

    brightness = float(np.mean(gray))
    fingerprint = _phash(analysis_image)

    checks = {}

    checks["dimensions"] = _check(
        "pass",
        "Image dimensions extracted successfully.",
        width=width,
        height=height,
        pixels=original_pixels,
    )

    checks["blur"] = _check(
        "pass" if blur_score >= 100 else "fail",
        (
            "Image sharpness is acceptable."
            if blur_score >= 100
            else "Image may be blurry."
        ),
        score=round(blur_score, 2),
        threshold=100,
    )

    brightness_status = (
        "pass" if 40 <= brightness <= 220 else "fail"
    )

    checks["brightness"] = _check(
        brightness_status,
        (
            "Image brightness is within the acceptable range."
            if brightness_status == "pass"
            else "Image may be too dark or overexposed."
        ),
        score=round(brightness, 2),
        minimum=40,
        maximum=220,
    )

    checks["duplicate_fingerprint"] = _check(
        "unknown",
        "Perceptual hash generated; duplicate comparison is performed by the worker.",
        phash=fingerprint,
    )

    ocr_result = _extract_text(analysis_image)

    if ocr_result["status"] == "completed":
        checks["ocr"] = _check(
            "pass",
            "OCR text extraction completed.",
            text=ocr_result["text"],
            confidence=ocr_result["confidence"],
            lines=ocr_result["lines"],
        )

        crop_results = _extract_plate_region_text(
            plate_search_image
        )

        all_candidates = []

        full_candidates = _detect_number_plates(
            ocr_result["lines"]
        )

        for candidate in full_candidates:
            candidate["source_region"] = "full_image"
            all_candidates.append(candidate)

        for crop_result in crop_results:
            crop_candidates = _detect_number_plates(
                crop_result["lines"]
            )

            for candidate in crop_candidates:
                candidate["source_region"] = crop_result["region"]
                candidate["preprocessing"] = crop_result["preprocessing"]
                all_candidates.append(candidate)

        # Keep the strongest candidate for each plate and region.
        deduplicated = {}

        for candidate in all_candidates:
            key = (
                candidate["plate"],
                candidate["source_region"],
            )

            existing = deduplicated.get(key)

            if (
                existing is None
                or candidate["candidate_confidence"]
                > existing["candidate_confidence"]
            ):
                deduplicated[key] = candidate

        plate_candidates = sorted(
            deduplicated.values(),
            key=lambda item: item["candidate_confidence"],
            reverse=True,
        )

        unique_plates = {
            item["plate"] for item in plate_candidates
        }

        has_unambiguous_match = (
            len(unique_plates) == 1
            and len(plate_candidates) > 0
            and any(
                item["direct_ocr_match"]
                and item["candidate_confidence"] >= 0.90
                for item in plate_candidates
            )
        )

        if has_unambiguous_match:
            plate_status = "pass"
            plate_message = (
                "A unique Indian number plate format was recognized."
            )

        elif plate_candidates:
            plate_status = "unknown"
            plate_message = (
                "Possible number plate detected, but OCR interpretation is ambiguous."
            )

        else:
            plate_status = "unknown"
            plate_message = (
                "No reliable number plate candidate was detected."
            )

        checks["number_plate"] = _check(
            plate_status,
            plate_message,
            candidates=plate_candidates,
            crop_regions_tested=len(crop_results),
            yellow_regions_detected=len(
                _detect_yellow_plate_regions(plate_search_image)
            ),
        )

    else:
        checks["ocr"] = _check(
            "skipped",
            "OCR processing could not be completed.",
            error=ocr_result.get("error"),
        )

        checks["number_plate"] = _check(
            "skipped",
            "Number plate detection skipped because OCR was unavailable.",
            candidates=[],
            crop_regions_tested=0,
            yellow_regions_detected=0,
        )

    return {
        "schema_version": "2.3",
        "image": {
            "width": width,
            "height": height,
            "file_size": path.stat().st_size,
        },
        "checks": checks,
        "summary": _build_summary(checks),
        "limitations": [
            "Number plate detection combines fixed crops, yellow-region proposals, two OCR preprocessing paths and format validation.",
            "Both CLAHE-only and adaptive-threshold variants are evaluated; this improves coverage but does not guarantee detection.",
            "Yellow-region localization may also select vehicle body panels or other yellow objects.",
            "The system does not verify vehicle registration against an official database.",
            "Small, occluded, rotated, reflective or distorted plates may not be detected.",
            "Ambiguous OCR candidates are reported as unknown rather than confirmed.",
            "Duplicate detection is performed against previously completed images.",
        ],
    }