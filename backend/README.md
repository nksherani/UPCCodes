# UPC Validator Backend

## Setup

```bash
cd upc-validator/backend
uv sync
```

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## Containerization

Build and run the API in Docker:

```bash
docker build -t upc-backend .
docker run --rm --name upc-backend -p 8000:8000 upc-backend
```

## Endpoints

- `POST /extract` with one or more PDF files (field name `files`)
- `POST /validate` with `spreadsheet` (Excel) and `metadata_json` (JSON string)
