import os
from pathlib import Path

from dotenv import load_dotenv

# Loads local .env for host development. Render injects environment variables directly.
load_dotenv()


class Settings:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://pipeline:pipeline@localhost:5432/media_pipeline",
    )
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    upload_dir = Path(os.getenv("UPLOAD_DIR", "data/uploads")).expanduser().resolve()

    storage_backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    r2_bucket_name = os.getenv("R2_BUCKET_NAME", "")
    r2_endpoint_url = os.getenv("R2_ENDPOINT_URL", "")
    r2_access_key_id = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY", "")
    r2_region = os.getenv("R2_REGION", "auto")

    max_upload_bytes = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    max_request_body_bytes = int(
        os.getenv("MAX_REQUEST_BODY_BYTES", str(max_upload_bytes + 1024 * 1024))
    )
    max_image_pixels = int(os.getenv("MAX_IMAGE_PIXELS", "50000000"))
    analysis_max_edge = int(os.getenv("ANALYSIS_MAX_EDGE", "1280"))
    max_attempts = int(os.getenv("MAX_ATTEMPTS", "3"))
    job_timeout_seconds = int(os.getenv("JOB_TIMEOUT_SECONDS", "300"))
    stale_processing_grace_seconds = int(os.getenv("STALE_PROCESSING_GRACE_SECONDS", "60"))


settings = Settings()
