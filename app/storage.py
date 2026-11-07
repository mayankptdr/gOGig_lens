from pathlib import Path
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from app.config import settings

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

def validate_upload(upload, content: bytes):
    if not content:
        raise ValueError("Uploaded file is empty")
    if len(content) > settings.max_upload_bytes:
        raise ValueError(f"File exceeds {settings.max_upload_bytes} byte limit")
    try:
        image = Image.open(BytesIO(content))
        image.verify()
        if image.format not in ALLOWED_FORMATS:
            raise ValueError("Only JPEG, PNG, and WEBP images are supported")
    except (UnidentifiedImageError, OSError):
        raise ValueError("File is not a valid supported image")

def save_upload(destination: Path, content: bytes):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
