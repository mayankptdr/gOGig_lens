
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app import worker as worker_module
from app.config import settings
from app.database import Base


@pytest.fixture
def test_environment(tmp_path, monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    # Isolate API and worker from the real database.
    monkeypatch.setattr(
        main_module,
        "SessionLocal",
        TestSessionLocal,
    )

    monkeypatch.setattr(
        worker_module,
        "SessionLocal",
        TestSessionLocal,
    )

    # Isolate upload storage.
    monkeypatch.setattr(
        settings,
        "upload_dir",
        upload_dir,
    )

    # Prevent real Redis queue operations.
    monkeypatch.setattr(
        main_module,
        "enqueue_image",
        lambda image_id: None,
    )

    monkeypatch.setattr(
        worker_module,
        "enqueue_image",
        lambda image_id, delay=0: None,
    )

    yield {
        "engine": test_engine,
        "SessionLocal": TestSessionLocal,
        "upload_dir": upload_dir,
    }

    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture
def client(test_environment):
    with TestClient(main_module.app) as test_client:
        yield test_client


@pytest.fixture
def valid_image_bytes():
    image = Image.new(
        "RGB",
        (300, 400),
        color="white",
    )

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")

    return buffer.getvalue()


@pytest.fixture
def uploaded_image(client, valid_image_bytes):
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

    return response.json()["processing_id"]
