
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status

from app.config import settings
from app.database import SessionLocal
from app.errors import UploadRejected
from app.models import ImageRecord
from app.schemas import UploadResponse, StatusResponse, AnalysisResponse
from app.storage import save_upload, get_storage_path
from app.queue import enqueue_image


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="gOGig Lens",
    version="2.0.0",
    description="Smart Image Analysis. Reliable Processing.",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/api/v1/images/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def upload_image(file: UploadFile = File(...)):
    image_id = str(uuid4())

    # 1. Validate and save image using chunked reading.
    try:
        storage_key, file_size = save_upload(file, image_id)
    except UploadRejected as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={
                "code": exc.code,
                "message": exc.message,
            },
        )
    finally:
        file.file.close()

    # 2. Persist upload metadata.
    db = SessionLocal()

    try:
        record = ImageRecord(
            id=image_id,
            original_filename=Path(file.filename or "upload").name[:255],
            content_type=file.content_type or "application/octet-stream",
            storage_key=storage_key,
            file_size=file_size,
            status="pending",
        )

        db.add(record)
        db.commit()

    except Exception:
        db.rollback()

        try:
            get_storage_path(storage_key).unlink(missing_ok=True)
        except (ValueError, OSError):
            pass

        raise HTTPException(
            status_code=500,
            detail="Could not persist upload metadata.",
        )

    finally:
        db.close()

    # 3. Enqueue background processing.
    try:
        enqueue_image(image_id)

    except Exception:
        db = SessionLocal()

        try:
            record = db.get(ImageRecord, image_id)

            if record:
                record.status = "failed"
                record.error_code = "analysis_error"
                record.error_message = (
                    "Image was stored but could not be queued."
                )
                db.commit()

        except Exception:
            db.rollback()

        finally:
            db.close()

        raise HTTPException(
            status_code=503,
            detail="Image was stored but could not be queued.",
        )

    return UploadResponse(
        processing_id=image_id,
        status="pending",
        message="Image accepted for asynchronous processing.",
    )


@app.get("/api/v1/images/{image_id}/status", response_model=StatusResponse)
def get_status(image_id: str):
    db = SessionLocal()

    try:
        record = db.get(ImageRecord, image_id)

        if not record:
            raise HTTPException(
                status_code=404,
                detail="Processing ID not found.",
            )

        return StatusResponse(
            processing_id=record.id,
            status=record.status,
            error=record.error_message,
            error_code=record.error_code,
            attempts=record.attempts,
            max_attempts=settings.max_attempts,
            started_at=record.started_at,
            finished_at=record.finished_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    finally:
        db.close()


@app.get("/api/v1/images/{image_id}/results", response_model=AnalysisResponse)
def get_results(image_id: str):
    db = SessionLocal()

    try:
        record = db.get(ImageRecord, image_id)

        if not record:
            raise HTTPException(
                status_code=404,
                detail="Processing ID not found.",
            )

        return AnalysisResponse(
            processing_id=record.id,
            status=record.status,
            analysis=record.analysis,
            error=record.error_message,
            error_code=record.error_code,
        )

    finally:
        db.close()
