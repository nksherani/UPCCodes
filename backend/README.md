# PDF Extractor API

FastAPI service that accepts a PDF, extracts text and embedded images, then OCRs each image and returns the results.

## Requirements

- Python 3.10+
- Tesseract OCR installed and available on PATH
  - macOS: `brew install tesseract`

## Install (uv)

```bash
cd /Users/naveed/repos/UPCCodes/backend
uv venv
uv pip install -e .
```

## Run

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Optional MongoDB

Set these env vars to enable persistence:

- `MONGODB_URI`
- `MONGODB_DB` (default `pdf_extractor`)
- `MONGODB_COLLECTION` (default `extractions`)
