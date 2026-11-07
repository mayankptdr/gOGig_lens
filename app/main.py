from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import ImageRecord
from app.schemas import UploadResponse, StatusResponse, AnalysisResponse
from app.storage import save_upload, validate_upload
from app.queue import enqueue_image

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="Intelligent Media Processing Pipeline",
    version="1.0.0",
    description="Asynchronous vehicle-image quality and authenticity screening API.",
    lifespan=lifespan,
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/v1/images/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_image(file: UploadFile = File(...)):
    content = await file.read()
    try:
        validate_upload(file, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    image_id = str(uuid4())
    suffix = Path(file.filename or "upload.jpg").suffix.lower() or ".jpg"
    destination = settings.upload_dir / f"{image_id}{suffix}"
    save_upload(destination, content)

    db = SessionLocal()
    try:
        record = ImageRecord(
            id=image_id,
            original_filename=(file.filename or "upload")[:255],
            content_type=file.content_type or "application/octet-stream",
            file_path=str(destination),
            file_size=len(content),
            status="pending",
        )
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not persist upload metadata")
    finally:
        db.close()

    try:
        enqueue_image(image_id)
    except Exception as exc:
        db = SessionLocal()
        try:
            record = db.get(ImageRecord, image_id)
            record.status = "failed"
            record.error_message = f"Queue submission failed: {type(exc).__name__}"
            db.commit()
        finally:
            db.close()
        raise HTTPException(status_code=503, detail="Image was stored but could not be queued")

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
            raise HTTPException(status_code=404, detail="Processing ID not found")
        return StatusResponse(
            processing_id=record.id,
            status=record.status,
            error=record.error_message,
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
            raise HTTPException(status_code=404, detail="Processing ID not found")
        if record.status in ("pending", "processing"):
            raise HTTPException(status_code=202, detail={"status": record.status, "message": "Analysis is not ready"})
        if record.status == "failed":
            raise HTTPException(status_code=422, detail={"status": "failed", "error": record.error_message})
        return AnalysisResponse(
            processing_id=record.id,
            status=record.status,
            analysis=record.analysis or {},
        )
    finally:
        db.close()
