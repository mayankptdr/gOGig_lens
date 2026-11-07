from pathlib import Path
from uuid import UUID
import warnings

from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.errors import UploadRejected


CHUNK_SIZE = 64 * 1024

FORMAT_EXTENSIONS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


def save_upload(upload, image_id: str) -> tuple[str, int]:
    """
    Stream an uploaded image to temporary storage, validate it,
    and atomically move it to its final storage location.

    Returns:
        (storage_key, file_size)
    """
    try:
        safe_id = str(UUID(image_id))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid image ID")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    temp_path = settings.upload_dir / f".{safe_id}.tmp"
    file_size = 0

    try:
        # Stream in chunks and enforce the actual file-size limit.
        with temp_path.open("xb") as destination:
            while True:
                chunk = upload.file.read(CHUNK_SIZE)

                if not chunk:
                    break

                file_size += len(chunk)

                if file_size > settings.max_upload_bytes:
                    raise UploadRejected("file_too_large", 413)

                destination.write(chunk)

        if file_size == 0:
            raise UploadRejected("empty_file", 400)

        # Inspect actual image content, not the supplied filename or MIME type.
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            try:
                with Image.open(temp_path) as image:
                    image_format = image.format

                    if image_format not in FORMAT_EXTENSIONS:
                        raise UploadRejected(
                            "unsupported_format",
                            415,
                        )

                    width, height = image.size

                    if width <= 0 or height <= 0:
                        raise UploadRejected("invalid_image", 400)

                    if width * height > settings.max_image_pixels:
                        raise UploadRejected(
                            "image_too_large_pixels",
                            413,
                        )

                    # Force decoding to detect truncated/corrupt images.
                    image.load()

            except UploadRejected:
                raise

            except (
                UnidentifiedImageError,
                Image.DecompressionBombError,
                Image.DecompressionBombWarning,
                OSError,
                ValueError,
            ):
                raise UploadRejected("invalid_image", 400)

        extension = FORMAT_EXTENSIONS[image_format]
        storage_key = f"{safe_id}{extension}"
        final_path = settings.upload_dir / storage_key

        # Atomic move after validation.
        temp_path.replace(final_path)

        return storage_key, file_size

    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def get_storage_path(storage_key: str) -> Path:
    """Resolve a storage key safely inside the upload directory."""
    if (
        not storage_key
        or Path(storage_key).name != storage_key
        or "/" in storage_key
        or "\\" in storage_key
    ):
        raise ValueError("Invalid storage key")

    base_dir = settings.upload_dir.resolve()
    file_path = (base_dir / storage_key).resolve()

    if file_path.parent != base_dir:
        raise ValueError("Invalid storage path")

    return file_path