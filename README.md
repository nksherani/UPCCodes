# PDF Extractor (FastAPI + React)

## Backend

```bash
cd /Users/naveed/repos/UPCCodes/backend
uv venv
uv pip install -e .
uv run dev
```

Backend runs at `http://localhost:8000`.

### Optional MongoDB

```bash
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DB="pdf_extractor"
export MONGODB_COLLECTION="extractions"
```

## Frontend

```bash
cd /Users/naveed/repos/UPCCodes/frontend
npm install
npm run dev
```

Optional env var in `frontend/.env`:

```
VITE_API_URL=http://localhost:8000
```

Frontend runs at `http://localhost:5173`.
