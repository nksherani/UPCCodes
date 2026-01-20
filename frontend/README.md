# UPC Validator Frontend

## Setup

```bash
cd upc-validator/frontend
npm install
```

## Run

```bash
npm run dev
```

Backend should be running at `http://localhost:8000`.

To point to a different backend, create `frontend/.env`:

```bash
VITE_API_BASE=https://your-backend-host
```

For Vercel, set `VITE_API_BASE=/api` and use the rewrite in `frontend/vercel.json`
to proxy to the backend (avoids mixed-content errors).
