import os
from pathlib import Path

class Settings:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://pipeline:pipeline@localhost:5432/media_pipeline",
    )
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    upload_dir = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
    max_upload_bytes = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

settings = Settings()
