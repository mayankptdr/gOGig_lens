
from datetime import datetime, timedelta, timezone

from app import worker
from app.config import settings
from app.models import ImageRecord


def create_record(
    test_environment,
    image_id,
    status="pending",
    attempts=0,
    storage_key="sample.jpg",
    started_at=None,
    analysis=None,
):
    db = test_environment["SessionLocal"]()

    try:
        record = ImageRecord(
            id=image_id,
            original_filename="sample.jpg",
            content_type="image/jpeg",
            storage_key=storage_key,
            file_size=100,
            status=status,
            attempts=attempts,
            started_at=started_at,
            analysis=analysis,
        )

        db.add(record)
        db.commit()

    finally:
        db.close()


def get_record(test_environment, image_id):
    db = test_environment["SessionLocal"]()

    try:
        return db.get(ImageRecord, image_id)
    finally:
        db.close()


def sample_analysis():
    return {
        "schema_version": "2.3",
        "checks": {
            "dimensions": {
                "status": "pass",
                "passed": True,
            },
            "duplicate_fingerprint": {
                "status": "pass",
                "passed": True,
                "phash": "a" * 64,
                "matches": [],
            },
        },
        "summary": {},
        "limitations": [],
    }


def test_worker_processes_image_successfully(
    test_environment,
    monkeypatch,
):
    image_id = "11111111-1111-1111-1111-111111111111"

    create_record(test_environment, image_id)

    image_path = test_environment["upload_dir"] / "sample.jpg"
    image_path.write_bytes(b"test-image")

    monkeypatch.setattr(
        worker,
        "analyze_image",
        lambda path: sample_analysis(),
    )

    worker.process_image(image_id)

    record = get_record(test_environment, image_id)

    assert record.status == "completed"
    assert record.attempts == 1
    assert record.analysis is not None
    assert record.finished_at is not None


def test_worker_retries_temporary_failure(
    test_environment,
    monkeypatch,
):
    image_id = "22222222-2222-2222-2222-222222222222"

    create_record(test_environment, image_id)

    image_path = test_environment["upload_dir"] / "sample.jpg"
    image_path.write_bytes(b"test-image")

    scheduled = []

    def failing_analysis(path):
        raise RuntimeError("Temporary processing failure")

    monkeypatch.setattr(
        worker,
        "analyze_image",
        failing_analysis,
    )

    monkeypatch.setattr(
        worker,
        "enqueue_image",
        lambda image_id, delay=0: scheduled.append(
            (image_id, delay)
        ),
    )

    worker.process_image(image_id)

    record = get_record(test_environment, image_id)

    assert record.status == "pending"
    assert record.attempts == 1
    assert record.error_code == "analysis_error"
    assert scheduled == [(image_id, 10)]


def test_worker_stops_after_maximum_attempts(
    test_environment,
    monkeypatch,
):
    image_id = "33333333-3333-3333-3333-333333333333"

    create_record(
        test_environment,
        image_id,
        attempts=2,
    )

    image_path = test_environment["upload_dir"] / "sample.jpg"
    image_path.write_bytes(b"test-image")

    scheduled = []

    monkeypatch.setattr(
        settings,
        "max_attempts",
        3,
    )

    def failing_analysis(path):
        raise RuntimeError("Processing failed")

    monkeypatch.setattr(
        worker,
        "analyze_image",
        failing_analysis,
    )

    monkeypatch.setattr(
        worker,
        "enqueue_image",
        lambda image_id, delay=0: scheduled.append(image_id),
    )

    worker.process_image(image_id)

    record = get_record(test_environment, image_id)

    assert record.status == "failed"
    assert record.attempts == 3
    assert record.error_code == "analysis_error"
    assert record.finished_at is not None
    assert scheduled == []


def test_worker_marks_missing_file_as_permanent_failure(
    test_environment,
):
    image_id = "44444444-4444-4444-4444-444444444444"

    create_record(test_environment, image_id)

    worker.process_image(image_id)

    record = get_record(test_environment, image_id)

    assert record.status == "failed"
    assert record.attempts == 1
    assert record.error_code == "file_missing"


def test_worker_detects_duplicate_fingerprint(
    test_environment,
    monkeypatch,
):
    existing_id = "55555555-5555-5555-5555-555555555555"
    new_id = "66666666-6666-6666-6666-666666666666"

    existing_analysis = sample_analysis()

    create_record(
        test_environment,
        existing_id,
        status="completed",
        analysis=existing_analysis,
    )

    create_record(test_environment, new_id)

    image_path = test_environment["upload_dir"] / "sample.jpg"
    image_path.write_bytes(b"test-image")

    monkeypatch.setattr(
        worker,
        "analyze_image",
        lambda path: sample_analysis(),
    )

    worker.process_image(new_id)

    record = get_record(test_environment, new_id)

    duplicate_check = record.analysis["checks"]["duplicate_fingerprint"]

    assert record.status == "completed"
    assert duplicate_check["status"] == "fail"
    assert duplicate_check["passed"] is False
    assert existing_id in duplicate_check["matches"]


def test_reaper_recovers_stale_jobs(
    test_environment,
    monkeypatch,
):
    retry_id = "77777777-7777-7777-7777-777777777777"
    failed_id = "88888888-8888-8888-8888-888888888888"

    monkeypatch.setattr(
        settings,
        "job_timeout_seconds",
        1,
    )

    monkeypatch.setattr(
        settings,
        "stale_processing_grace_seconds",
        1,
    )

    monkeypatch.setattr(
        settings,
        "max_attempts",
        3,
    )

    stale_time = datetime.now(timezone.utc) - timedelta(minutes=5)

    create_record(
        test_environment,
        retry_id,
        status="processing",
        attempts=1,
        started_at=stale_time,
    )

    create_record(
        test_environment,
        failed_id,
        status="processing",
        attempts=3,
        started_at=stale_time,
    )

    scheduled = []

    monkeypatch.setattr(
        worker,
        "enqueue_image",
        lambda image_id, delay=0: scheduled.append(
            (image_id, delay)
        ),
    )

    result = worker.recover_stale_jobs()

    retry_record = get_record(test_environment, retry_id)
    failed_record = get_record(test_environment, failed_id)

    assert result["stale_jobs_found"] == 2
    assert result["retries_scheduled"] == 1
    assert result["jobs_failed"] == 1

    assert retry_record.status == "pending"
    assert retry_record.error_code == "worker_lost"

    assert failed_record.status == "failed"
    assert failed_record.error_code == "worker_lost"

    assert scheduled == [(retry_id, 10)]
