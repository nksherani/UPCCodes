import os
import tempfile
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.extractors.carelabel import extract_care_labels
from app.extractors.classifier import classify_pdf
from app.extractors.rfid import extract_hang_tags

app = FastAPI(title="UPC Validator API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _save_upload(file: UploadFile) -> str:
    suffix = ".pdf" if file.filename and file.filename.lower().endswith(".pdf") else ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        return tmp.name


def _normalize_items(items: list[dict[str, Any]], parent_info: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = []
    for item in items:
        raw_item = dict(item)
        raw_item.pop("composition", None)
        merged = {
            "style_number": item.get("style_number") or parent_info.get("style_number"),
            "size": item.get("size"),
            "color": item.get("color") or parent_info.get("color"),
            "upc": item.get("upc") or item.get("barcode") or item.get("upc_candidate"),
            "raw": raw_item,
        }
        normalized.append(merged)
    return normalized


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/extract")
def extract(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    care_labels: list[dict[str, Any]] = []
    hang_tags: list[dict[str, Any]] = []

    for file in files:
        if file.content_type not in {"application/pdf", "application/x-pdf"}:
            raise HTTPException(status_code=400, detail=f"Unsupported file: {file.filename}")

        tmp_path = _save_upload(file)
        try:
            classification = classify_pdf(tmp_path)
            if classification["type"] == "care_label":
                metadata = extract_care_labels(tmp_path)
                care_labels.extend(_normalize_items(metadata["care_labels"], metadata["parent_info"]))
            elif classification["type"] == "rfid":
                metadata = extract_hang_tags(tmp_path)
                hang_tags.extend(_normalize_items(metadata["hang_tags"], metadata["parent_info"]))
            else:
                metadata = extract_care_labels(tmp_path)
                if metadata["care_labels"]:
                    care_labels.extend(_normalize_items(metadata["care_labels"], metadata["parent_info"]))
                else:
                    metadata = extract_hang_tags(tmp_path)
                    hang_tags.extend(_normalize_items(metadata["hang_tags"], metadata["parent_info"]))
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return {
        "care_labels": care_labels,
        "hang_tags": hang_tags,
    }


