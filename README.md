# Intelligent Media Processing Pipeline

Asynchronous vehicle-image screening API built with FastAPI, PostgreSQL, Redis/RQ and OpenCV.

## Features
- Image upload with format and size validation
- UUID processing ID and metadata persistence
- Redis/RQ background processing
- Status and results endpoints
- Blur, brightness, dimensions and perceptual-hash checks
- Explicit uncertainty and limitations in results
- Docker Compose setup and a starter unit test

## Architecture
1. API validates the image and stores it in shared local storage.
2. API persists metadata with `pending` status in PostgreSQL.
3. API enqueues the image ID in Redis/RQ and returns HTTP 202.
4. Worker loads the record, marks it `processing`, runs image checks, then stores structured results and marks it `completed`.
5. Clients poll status and fetch results from the API.

The API and worker share the upload volume. For production, replace local storage with object storage and use a transactional outbox to avoid the database/queue dual-write gap.

## Run with Docker
```bash
docker compose up --build
```
Open Swagger UI at http://localhost:8000/docs.

## Run locally (Windows PowerShell)
Start PostgreSQL and Redis first, then:
```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```
In a second terminal:
```powershell
.venv\Scripts\Activate.ps1
rq worker image-processing --url redis://localhost:6379/0
```

## API
### Upload
```bash
curl -X POST "http://localhost:8000/api/v1/images/upload" -F "file=@vehicle.jpg"
```
Returns `202 Accepted` with `processing_id`.

### Status
```bash
curl "http://localhost:8000/api/v1/images/{processing_id}/status"
```

### Results
```bash
curl "http://localhost:8000/api/v1/images/{processing_id}/results"
```

## Status lifecycle
`pending -> processing -> completed | failed`

## Checks and uncertainty
- Blur: Laplacian variance heuristic.
- Brightness: mean grayscale intensity heuristic.
- Dimensions: minimum 300x300.
- Duplicate fingerprint: pHash is generated. Cross-upload duplicate matching is a next implementation step.
- OCR and plate format: documented placeholders until an OCR engine is configured.

Do not interpret the screening score as a probability of fraud or image authenticity.

## Trade-offs and next steps
- Local disk storage is suitable for a take-home demo; use S3-compatible object storage in production.
- Add persistent pHash indexing and Hamming-distance duplicate lookup.
- Add OCR (Tesseract/EasyOCR) and normalize plate strings before regex validation.
- Improve retry semantics with attempt tracking and only mark failed after the final retry.
- Add DB migrations (Alembic), authentication, rate limiting and file-retention policies.
- Add transactional outbox to ensure queued jobs are not lost between DB commit and Redis enqueue.
- Calibrate thresholds against labelled vehicle images.

## AI usage disclosure
Complete this section truthfully before submission:
- AI tools used:
- What AI helped with:
- Suggestions rejected or corrected:
- How generated code was validated (tests, manual API checks, edge cases):

## Assumptions
- Inputs are JPEG, PNG or WEBP images up to 10 MB.
- The system is a screening aid, not a fraud verdict.
- Vehicle plate OCR depends on adding and configuring an OCR engine.


## Streamlit frontend
Run the dashboard in a second terminal while the API and worker are running:
```powershell
streamlit run streamlit_app.py
```
Set `API_BASE_URL` if the FastAPI backend is not at `http://localhost:8000`.
The UI provides an overview, image upload, automatic status polling, and processing/result lookup.
