
from app.models import ImageRecord


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_valid_image_upload(client, valid_image_bytes):
    response = client.post(
        "/api/v1/images/upload",
        files={
            "file": (
                "sample.jpg",
                valid_image_bytes,
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 202

    data = response.json()

    assert data["processing_id"]
    assert data["status"] == "pending"
    assert data["message"]


def test_upload_persists_database_record(
    client,
    uploaded_image,
    test_environment,
):
    db = test_environment["SessionLocal"]()

    try:
        record = db.get(ImageRecord, uploaded_image)

        assert record is not None
        assert record.status == "pending"
        assert record.original_filename == "sample.jpg"
        assert record.file_size > 0

    finally:
        db.close()


def test_upload_rejects_empty_file(client):
    response = client.post(
        "/api/v1/images/upload",
        files={
            "file": (
                "empty.jpg",
                b"",
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "empty_file"


def test_upload_rejects_non_image_file(client):
    response = client.post(
        "/api/v1/images/upload",
        files={
            "file": (
                "document.txt",
                b"This is not an image.",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_image"


def test_status_endpoint(client, uploaded_image):
    response = client.get(
        f"/api/v1/images/{uploaded_image}/status"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["processing_id"] == uploaded_image
    assert data["status"] == "pending"
    assert data["attempts"] == 0
    assert "max_attempts" in data
    assert "created_at" in data


def test_results_endpoint(client, uploaded_image):
    response = client.get(
        f"/api/v1/images/{uploaded_image}/results"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["processing_id"] == uploaded_image
    assert data["status"] == "pending"
    assert data["analysis"] is None


def test_unknown_status_returns_404(client):
    response = client.get(
        "/api/v1/images/00000000-0000-0000-0000-000000000000/status"
    )

    assert response.status_code == 404


def test_unknown_results_returns_404(client):
    response = client.get(
        "/api/v1/images/00000000-0000-0000-0000-000000000000/results"
    )

    assert response.status_code == 404
