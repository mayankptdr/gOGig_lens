
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.config import settings
from app.database import SessionLocal
from app.errors import PermanentProcessingError
from app.models import ImageRecord
from app.storage import download_storage_file
from app.analyzer import analyze_image
from app.queue import enqueue_image


logger = logging.getLogger("image-worker")

DUPLICATE_DISTANCE_THRESHOLD = 5


def _hamming_distance(left: str, right: str) -> int:
    """Calculate the Hamming distance between two perceptual hashes."""
    if len(left) != len(right):
        return max(len(left), len(right))

    return sum(a != b for a, b in zip(left, right))


def _refresh_summary(result: dict) -> None:
    """Recalculate summary metrics from actual check statuses."""

    checks = result.get("checks", {})

    passed = [
        name for name, check in checks.items()
        if check.get("status") == "pass"
    ]

    failed = [
        name for name, check in checks.items()
        if check.get("status") == "fail"
    ]

    skipped = [
        name for name, check in checks.items()
        if check.get("status") == "skipped"
    ]

    unknown = [
        name for name, check in checks.items()
        if check.get("status") == "unknown"
    ]

    total = len(checks)
    evaluated = len(passed) + len(failed)

    confidence = (
        round(len(passed) / evaluated, 4)
        if evaluated > 0 else 0.0
    )

    result["summary"] = {
        "checks_passed": len(passed),
        "checks_failed": len(failed),
        "checks_skipped": len(skipped),
        "checks_unknown": len(unknown),
        "total_checks": total,
        "evaluated_checks": evaluated,
        "confidence": confidence,
        "flagged_checks": failed,
        "skipped_checks": skipped,
        "unknown_checks": unknown,
        "checks_total": total,
        "checks_evaluated": evaluated,
        "confidence_score": confidence,
    }


def _claim_job(db, image_id: str) -> int | None:
    """Atomically claim a pending job."""

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
    """Compare current perceptual hash with completed uploads."""

    fingerprint = result.get("checks", {}).get(
        "duplicate_fingerprint", {}
    )

    new_hash = fingerprint.get("phash")

    if not new_hash:
        fingerprint.update({
            "status": "skipped",
            "passed": None,
            "matches": [],
            "message": "Duplicate fingerprint unavailable.",
        })
        _refresh_summary(result)
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

    is_duplicate = bool(matches)

    fingerprint.update({
        "status": "fail" if is_duplicate else "pass",
        "passed": not is_duplicate,
        "matches": matches,
        "hamming_distance_threshold": DUPLICATE_DISTANCE_THRESHOLD,
        "message": (
            "Potential duplicate detected against previous uploads."
            if is_duplicate
            else "No near-duplicate found among previous completed uploads."
        ),
    })

    _refresh_summary(result)


def _mark_failed(
    db,
    image_id: str,
    error_code: str,
    message: str,
    allowed_statuses=("processing",),
) -> None:
    """Mark a job as failed only if it is in an allowed state."""

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
    """Process one image with atomic claiming and bounded retries."""

    db = SessionLocal()
    claimed = False

    try:
        logger.info("Starting image processing: %s", image_id)

        # 1. Atomically claim the job.
        attempt_number = _claim_job(db, image_id)

        if attempt_number is None:
            logger.info(
                "Job %s is already claimed or not pending.",
                image_id,
            )
            return

        claimed = True

        logger.info(
            "Job claimed: image_id=%s attempt=%s/%s",
            image_id,
            attempt_number,
            settings.max_attempts,
        )

        record = db.get(ImageRecord, image_id)

        if record is None:
            logger.error("Image record does not exist: %s", image_id)
            return

        # 2. Download image from configured storage.
        logger.info(
            "Downloading image from storage: %s",
            image_id,
        )

        with download_storage_file(record.storage_key) as image_path:

            if not image_path.is_file():
                raise PermanentProcessingError("file_missing")

            logger.info(
                "Image downloaded successfully: %s",
                image_id,
            )

            # 3. Run image analysis.
            logger.info("Starting image analysis: %s", image_id)

            analysis_result = analyze_image(str(image_path))

            logger.info("Image analysis finished: %s", image_id)

        # 4. Duplicate detection.
        logger.info("Checking duplicate fingerprint: %s", image_id)

        _compare_duplicates(db, image_id, analysis_result)

        # 5. Save analysis and mark completed.
        save_result = db.execute(
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

        if save_result.rowcount == 1:
            logger.info(
                "IMAGE PROCESSING COMPLETED SUCCESSFULLY: %s",
                image_id,
            )
        else:
            logger.warning(
                "Image %s was no longer processing when result was saved.",
                image_id,
            )

    except Exception as exc:

        # Log the actual exception and complete traceback.
        logger.exception(
            "IMAGE PROCESSING ERROR | image_id=%s | error=%s",
            image_id,
            exc,
        )

        db.rollback()

        if not claimed:
            raise

        # 6. Classify the error.
        if isinstance(exc, PermanentProcessingError):
            error_code = exc.code
            error_message = exc.message
            permanent_error = True

        elif isinstance(exc, FileNotFoundError):
            error_code = "file_missing"
            error_message = (
                "The stored image file could not be found."
            )
            permanent_error = True

        elif isinstance(exc, ValueError):
            error_code = "decode_failed"
            error_message = (
                "The stored image could not be decoded."
            )
            permanent_error = True

        else:
            error_code = "analysis_error"
            error_message = (
                "Image processing encountered a temporary error."
            )
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
                db,
                image_id,
                error_code,
                error_message,
            )

            logger.error(
                "Image %s failed after %s attempts.",
                image_id,
                record.attempts,
            )
            return

        # 7. Return job to pending.
        retry_update = db.execute(
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

        if retry_update.rowcount != 1:
            logger.warning(
                "Could not return job %s to pending for retry.",
                image_id,
            )
            return

        retry_delay = 10 if record.attempts == 1 else 30

        # 8. Schedule retry.
        try:
            enqueue_image(
                image_id,
                delay=retry_delay,
            )

            logger.warning(
                "Retry scheduled: image_id=%s attempt=%s/%s delay=%ss",
                image_id,
                record.attempts,
                settings.max_attempts,
                retry_delay,
            )

        except Exception:
            logger.exception(
                "Retry enqueue failed: %s",
                image_id,
            )

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
    """Recover jobs left processing after a worker crash."""

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
                    "Could not enqueue recovered job: %s",
                    image_id,
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

        logger.info(
            "Stale-job recovery completed: %s",
            summary,
        )

        return summary

    except Exception:
        db.rollback()
        logger.exception("Stale-job recovery failed.")
        raise

    finally:
        db.close()
