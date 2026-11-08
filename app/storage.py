from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID
import warnings

import boto3
from botocore.config import Config
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.errors import UploadRejected

CHUNK_SIZE = 64 * 1024

FORMAT_EXTENSIONS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


def _r2_client():
    """Create an S3-compatible Cloudflare R2 client."""
    required = (
        settings.r2_endpoint_url,
        settings.r2_access_key_id,
        settings.r2_secret_access_key,
        settings.r2_bucket_name,
    )
    if not all(required):
        raise RuntimeError("R2 storage is selected but R2 credentials are incomplete.")

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name=settings.r2_region or "auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def _is_r2() -> bool:
    return settings.storage_backend.lower() == "r2"


def _safe_image_id(image_id: str) -> str:
    try:
        return str(UUID(image_id))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid image ID")


def save_upload(upload, image_id: str) -> tuple[str, int]:
    """
    Stream and validate an uploaded image before storing it.

    Returns (storage_key, file_size). In R2 mode, validation happens in a
    temporary local file and the validated object is then uploaded privately.
    """
    safe_id = _safe_image_id(image_id)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    temp_path = settings.upload_dir / f".{safe_id}.tmp"
    file_size = 0

    try:
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

        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            try:
                with Image.open(temp_path) as image:
                    image_format = image.format
                    if image_format not in FORMAT_EXTENSIONS:
                        raise UploadRejected("unsupported_format", 415)
                    width, height = image.size
                    if width <= 0 or height <= 0:
                        raise UploadRejected("invalid_image", 400)
                    if width * height > settings.max_image_pixels:
                        raise UploadRejected("image_too_large_pixels", 413)
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

        storage_key = f"{safe_id}{FORMAT_EXTENSIONS[image_format]}"

        if _is_r2():
            _r2_client().upload_file(
                str(temp_path),
                settings.r2_bucket_name,
                storage_key,
                ExtraArgs={"ContentType": f"image/{'jpeg' if image_format == 'JPEG' else image_format.lower()}"},
            )
            temp_path.unlink(missing_ok=True)
        else:
            final_path = get_storage_path(storage_key)
            temp_path.replace(final_path)

        return storage_key, file_size

    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def get_storage_path(storage_key: str) -> Path:
    """Resolve a storage key safely inside the local upload directory."""
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


def delete_storage_object(storage_key: str) -> None:
    """Delete an object from the configured storage backend."""
    if _is_r2():
        _r2_client().delete_object(
            Bucket=settings.r2_bucket_name,
            Key=storage_key,
        )
    else:
        get_storage_path(storage_key).unlink(missing_ok=True)


@contextmanager
def download_storage_file(storage_key: str):
    """
    Yield a local filesystem path for analysis.
    R2 objects are downloaded to a temporary file and removed afterwards.
    """
    if not _is_r2():
        path = get_storage_path(storage_key)
        if not path.is_file():
            raise FileNotFoundError(storage_key)
        yield path
        return

    # Validate key before using it in the object-store request.
    if (
        not storage_key
        or Path(storage_key).name != storage_key
        or "/" in storage_key
        or "\\" in storage_key
    ):
        raise ValueError("Invalid storage key")

    suffix = Path(storage_key).suffix
    temp_path = None
    try:
        with NamedTemporaryFile(prefix="gogig-", suffix=suffix, delete=False) as temp:
            temp_path = Path(temp.name)
        _r2_client().download_file(
            settings.r2_bucket_name,
            storage_key,
            str(temp_path),
        )
        yield temp_path
    except Exception as exc:
        # Normalize a missing R2 object into the worker's existing permanent error path.
        response = getattr(exc, "response", {})
        code = str(response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            raise FileNotFoundError(storage_key) from exc
        raise
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
