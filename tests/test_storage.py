
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app import storage
from app.config import settings
from app.errors import UploadRejected


def create_image_bytes(
    image_format="JPEG",
    size=(100, 100),
):
    buffer = BytesIO()
    image = Image.new("RGB", size, color="white")
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def create_upload(data):
    return SimpleNamespace(file=BytesIO(data))


def test_valid_image_is_saved_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    image_id = "12345678-1234-5678-1234-567812345678"
    image_bytes = create_image_bytes()

    storage_key, file_size = storage.save_upload(
        create_upload(image_bytes),
        image_id,
    )

    saved_path = tmp_path / storage_key

    assert saved_path.exists()
    assert file_size == len(image_bytes)
    assert saved_path.read_bytes() == image_bytes
    assert storage_key.endswith(".jpg")
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".*.tmp"))


def test_upload_rejects_file_exceeding_size_limit(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "max_upload_bytes", 100)

    image_bytes = create_image_bytes(size=(200, 200))

    with pytest.raises(UploadRejected):
        storage.save_upload(
            create_upload(image_bytes),
            "12345678-1234-5678-1234-567812345678",
        )

    assert not list(tmp_path.iterdir())


def test_upload_rejects_image_exceeding_pixel_limit(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "max_upload_bytes", 10 * 1024 * 1024)
    monkeypatch.setattr(settings, "max_image_pixels", 100)

    image_bytes = create_image_bytes(size=(20, 20))

    with pytest.raises(UploadRejected):
        storage.save_upload(
            create_upload(image_bytes),
            "12345678-1234-5678-1234-567812345678",
        )

    assert not list(tmp_path.iterdir())


def test_upload_rejects_unsupported_image_format(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    image_bytes = create_image_bytes(image_format="GIF")

    with pytest.raises(UploadRejected):
        storage.save_upload(
            create_upload(image_bytes),
            "12345678-1234-5678-1234-567812345678",
        )

    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "storage_key",
    [
        "../outside.jpg",
        "..\\outside.jpg",
        "folder/image.jpg",
        "C:\\outside.jpg",
        "",
    ],
)
def test_storage_path_rejects_unsafe_keys(
    tmp_path,
    monkeypatch,
    storage_key,
):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    with pytest.raises(ValueError):
        storage.get_storage_path(storage_key)


def test_failed_upload_cleans_temporary_file(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    invalid_bytes = b"this is not a valid image"

    with pytest.raises(UploadRejected):
        storage.save_upload(
            create_upload(invalid_bytes),
            "12345678-1234-5678-1234-567812345678",
        )

    assert not list(tmp_path.iterdir())
