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

## Endpoints

- `POST /extract` with one or more PDF files (field name `files`)
- `POST /validate` with `spreadsheet` (Excel) and `metadata_json` (JSON string)
