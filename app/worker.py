import logging
from app.database import SessionLocal
from app.models import ImageRecord
from app.analyzer import analyze_image

logger = logging.getLogger("image-worker")

def _hamming_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        return max(len(left), len(right))
    return sum(a != b for a, b in zip(left, right))

def process_image(image_id: str):
    db = SessionLocal()
    try:
        record = db.get(ImageRecord, image_id)
        if record is None:
            logger.error("Image record %s does not exist", image_id)
            return
        if record.status == "completed":
            return

        record.status = "processing"
        record.error_message = None
        db.commit()

        result = analyze_image(record.file_path)

        # Compare the new perceptual hash against completed uploads.
        new_hash = result["checks"]["duplicate_fingerprint"]["phash"]
        candidates = db.query(ImageRecord).filter(
            ImageRecord.id != image_id,
            ImageRecord.status == "completed",
            ImageRecord.analysis.isnot(None),
        ).all()
        matches = []
        for candidate in candidates:
            old_hash = (
                (candidate.analysis or {})
                .get("checks", {})
                .get("duplicate_fingerprint", {})
                .get("phash")
            )
            if old_hash and _hamming_distance(new_hash, old_hash) <= 5:
                matches.append(candidate.id)

        result["checks"]["duplicate_fingerprint"].update({
            "passed": len(matches) == 0,
            "matches": matches,
            "hamming_distance_threshold": 5,
            "message": "Perceptual hash compared with previously completed uploads; near matches are flagged.",
        })
        if matches:
            result["summary"]["flagged_checks"].append("duplicate_fingerprint")
            result["summary"]["checks_passed"] -= 1
            result["summary"]["confidence_score"] = round(
                result["summary"]["checks_passed"] / result["summary"]["checks_total"], 2
            )

        record.analysis = result
        record.status = "completed"
        db.commit()
        logger.info("Image processing completed: %s", image_id)
    except Exception as exc:
        db.rollback()
        record = db.get(ImageRecord, image_id)
        if record:
            record.status = "failed"
            record.error_message = f"{type(exc).__name__}: {str(exc)[:500]}"
            db.commit()
        logger.exception("Image processing failed: %s", image_id)
        raise
    finally:
        db.close()
