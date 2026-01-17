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

## Barcode Decoding (rfid.py)

If you want barcode decoding via `pyzbar`, install the system `zbar` library:

```bash
brew install zbar
```

Then install the Python package in the `Files` venv:

```bash
cd /Users/naveed/repos/UPCCodes/Files
uv pip install pyzbar
```

If Python still says it cannot find the zbar shared library, add Homebrew's
lib path for dynamic loading:

```bash
# Apple Silicon
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"

# Intel
export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
```

To persist

```bash
echo 'export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"' >> /Users/naveed/.zshrc
source ~/.zshrc
```
