
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.config import settings
from app.database import SessionLocal
from app.errors import PermanentProcessingError
from app.models import ImageRecord
from app.storage import get_storage_path
from app.analyzer import analyze_image
from app.queue import enqueue_image


logger = logging.getLogger("image-worker")

DUPLICATE_DISTANCE_THRESHOLD = 5


def _hamming_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        return max(len(left), len(right))
    return sum(a != b for a, b in zip(left, right))


def _claim_job(db, image_id: str) -> int | None:
    result = db.execute(
        update(ImageRecord)
        .where(
            ImageRecord.id == image_id,
            ImageRecord.status == "pending",
        )
        .values(
            status="processing",
            attempts=ImageRecord.attempts + 1,
            started_at=datetime.now(timezone.utc),
            finished_at=None,
            error_message=None,
            error_code=None,
        )
    )

    db.commit()

    if result.rowcount != 1:
        return None

    record = db.get(ImageRecord, image_id)
    return record.attempts if record else None


def _compare_duplicates(db, image_id: str, result: dict) -> None:
    fingerprint = result.get("checks", {}).get(
        "duplicate_fingerprint", {}
    )
    new_hash = fingerprint.get("phash")

    if not new_hash:
        return

    candidates = (
        db.query(ImageRecord)
        .filter(
            ImageRecord.id != image_id,
            ImageRecord.status == "completed",
            ImageRecord.analysis.isnot(None),
        )
        .all()
    )

    matches = []

    for candidate in candidates:
        old_hash = (
            (candidate.analysis or {})
            .get("checks", {})
            .get("duplicate_fingerprint", {})
            .get("phash")
        )

        if (
            old_hash
            and _hamming_distance(new_hash, old_hash)
            <= DUPLICATE_DISTANCE_THRESHOLD
        ):
            matches.append(candidate.id)

    was_passed = fingerprint.get("passed", True)

    fingerprint.update({
        "passed": len(matches) == 0,
        "matches": matches,
        "hamming_distance_threshold": DUPLICATE_DISTANCE_THRESHOLD,
        "message": (
            "Perceptual hash compared with previously completed "
            "uploads; near matches are flagged."
        ),
    })

    if matches and was_passed:
        summary = result.get("summary", {})
        flagged = summary.setdefault("flagged_checks", [])

        if "duplicate_fingerprint" not in flagged:
            flagged.append("duplicate_fingerprint")
            summary["checks_passed"] = max(
                0, summary.get("checks_passed", 0) - 1
            )

        total = summary.get("checks_total", 0)

        if total:
            summary["confidence_score"] = round(
                summary["checks_passed"] / total, 2
            )


def _mark_failed(
    db,
    image_id: str,
    error_code: str,
    message: str,
    allowed_statuses=("processing",),
) -> None:
    db.execute(
        update(ImageRecord)
        .where(
            ImageRecord.id == image_id,
            ImageRecord.status.in_(allowed_statuses),
        )
        .values(
            status="failed",
            error_code=error_code,
            error_message=message,
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def process_image(image_id: str):
    db = SessionLocal()
    claimed = False

    try:
        # 1. Atomically claim a pending job.
        attempt_number = _claim_job(db, image_id)

        if attempt_number is None:
            logger.info("Job %s is already claimed or not pending.", image_id)
            return

        claimed = True

        record = db.get(ImageRecord, image_id)

        if record is None:
            logger.error("Image record %s does not exist.", image_id)
            return

        # 2. Resolve stored image safely.
        image_path = get_storage_path(record.storage_key)

        if not image_path.is_file():
            raise PermanentProcessingError("file_missing")

        # 3. Analyze image.
        analysis_result = analyze_image(str(image_path))

        # 4. Compare duplicate fingerprints.
        _compare_duplicates(db, image_id, analysis_result)

        # 5. Save result.
        result = db.execute(
            update(ImageRecord)
            .where(
                ImageRecord.id == image_id,
                ImageRecord.status == "processing",
            )
            .values(
                analysis=analysis_result,
                status="completed",
                error_message=None,
                error_code=None,
                finished_at=datetime.now(timezone.utc),
            )
        )

        db.commit()

        if result.rowcount == 1:
            logger.info("Image processing completed: %s", image_id)

    except Exception as exc:
        db.rollback()

        if not claimed:
            logger.exception("Could not claim job %s.", image_id)
            raise

        # 6. Classify the error.
        if isinstance(exc, PermanentProcessingError):
            error_code = exc.code
            error_message = exc.message
            permanent_error = True

        elif isinstance(exc, FileNotFoundError):
            error_code = "file_missing"
            error_message = "The stored image file could not be found."
            permanent_error = True

        elif isinstance(exc, ValueError):
            error_code = "decode_failed"
            error_message = "The stored image could not be decoded."
            permanent_error = True

        else:
            error_code = "analysis_error"
            error_message = "Image processing encountered a temporary error."
            permanent_error = False

        record = db.get(ImageRecord, image_id)

        if record is None:
            logger.error("Record disappeared: %s", image_id)
            raise

        should_retry = (
            not permanent_error
            and record.attempts < settings.max_attempts
        )

        if not should_retry:
            _mark_failed(
                db, image_id, error_code, error_message
            )
            logger.error(
                "Image %s failed permanently after %s attempts.",
                image_id,
                record.attempts,
            )
            return

        # 7. Return job to pending.
        db.execute(
            update(ImageRecord)
            .where(
                ImageRecord.id == image_id,
                ImageRecord.status == "processing",
            )
            .values(
                status="pending",
                error_code=error_code,
                error_message=error_message,
                finished_at=None,
            )
        )
        db.commit()

        retry_delay = 10 if record.attempts == 1 else 30

        # 8. Schedule the next attempt.
        try:
            enqueue_image(image_id, delay=retry_delay)

            logger.warning(
                "Retry scheduled for %s. Attempt %s/%s.",
                image_id,
                record.attempts,
                settings.max_attempts,
            )

        except Exception:
            logger.exception("Retry enqueue failed for %s.", image_id)

            db.rollback()

            _mark_failed(
                db,
                image_id,
                "analysis_error",
                "Processing failed and retry could not be scheduled.",
                allowed_statuses=("pending",),
            )

    finally:
        db.close()


def recover_stale_jobs() -> dict:
    """
    Recover jobs left in processing after a worker crash.

    A job is stale only after its configured execution timeout
    plus the additional grace period.
    """
    db = SessionLocal()

    now = datetime.now(timezone.utc)

    stale_after = (
        settings.job_timeout_seconds
        + settings.stale_processing_grace_seconds
    )

    cutoff = now - timedelta(seconds=stale_after)

    retry_ids = []
    failed_count = 0

    try:
        # Lock selected rows to avoid concurrent reapers.
        stale_records = db.execute(
            select(ImageRecord)
            .where(
                ImageRecord.status == "processing",
                ImageRecord.started_at.isnot(None),
                ImageRecord.started_at < cutoff,
            )
            .with_for_update(skip_locked=True)
        ).scalars().all()

        for record in stale_records:
            if record.attempts < settings.max_attempts:
                record.status = "pending"
                record.error_code = "worker_lost"
                record.error_message = (
                    "The processing worker stopped unexpectedly. "
                    "The job will be retried."
                )
                record.finished_at = None
                retry_ids.append(record.id)

            else:
                record.status = "failed"
                record.error_code = "worker_lost"
                record.error_message = (
                    "The processing worker stopped unexpectedly "
                    "after the maximum number of attempts."
                )
                record.finished_at = now
                failed_count += 1

        db.commit()

        scheduled_count = 0

        for image_id in retry_ids:
            try:
                enqueue_image(image_id, delay=10)
                scheduled_count += 1

            except Exception:
                logger.exception(
                    "Could not enqueue recovered job %s.", image_id
                )

                _mark_failed(
                    db,
                    image_id,
                    "worker_lost",
                    "Worker stopped unexpectedly and recovery enqueue failed.",
                    allowed_statuses=("pending",),
                )

        summary = {
            "stale_jobs_found": len(stale_records),
            "retries_scheduled": scheduled_count,
            "jobs_failed": failed_count,
        }

        logger.info("Stale-job recovery completed: %s", summary)
        return summary

    except Exception:
        db.rollback()
        logger.exception("Stale-job recovery failed.")
        raise

    finally:
        db.close()
