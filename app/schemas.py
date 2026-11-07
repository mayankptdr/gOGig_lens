
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


ProcessingStatus = Literal[
    "pending",
    "processing",
    "completed",
    "failed",
]


class UploadResponse(BaseModel):
    processing_id: str
    status: ProcessingStatus
    message: str


class StatusResponse(BaseModel):
    processing_id: str
    status: ProcessingStatus
    error: str | None = None
    error_code: str | None = None
    attempts: int
    max_attempts: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AnalysisResponse(BaseModel):
    processing_id: str
    status: ProcessingStatus
    analysis: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None
