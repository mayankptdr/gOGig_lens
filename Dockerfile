
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Native runtime libraries required by OpenCV.

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libxcb1 \
        libglib2.0-0 \
        libgl1 \
        libsm6 \
        libxext6 && \
    rm -rf /var/lib/apt/lists/*


COPY requirements.txt .

RUN python -m pip install \
    --retries 3 \
    --timeout 60 \
    -r requirements.txt

RUN groupadd --system appuser && \
    useradd --system --gid appuser --home-dir /app appuser && \
    mkdir -p /app/data/uploads && \
    chown -R appuser:appuser /app

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
