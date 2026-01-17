import base64
import os
import re
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient

load_dotenv()

app = FastAPI(title="PDF Extractor API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "pdf_extractor")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "extractions")


def _get_collection():
    if not MONGODB_URI:
        return None
    client = MongoClient(MONGODB_URI)
    return client[MONGODB_DB][MONGODB_COLLECTION]


def _render_page_image(page: fitz.Page, zoom: float = 2.0) -> bytes:
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)
    return pix.tobytes("png")


def _normalize_text(text: str) -> str:
    text = re.sub(r"[^\x20-\x7E]", " ", text)
    text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)
    return text


def _extract_upc_ean(text: str) -> list[str]:
    normalized = _normalize_text(text)
    pattern = re.compile(r"(?:EAN\/?UPC|EANIUPC)?\s*(\d{12,13})")
    return pattern.findall(normalized)


def _is_valid_upc_ean(code: str) -> bool:
    digits = list(map(int, code))
    check = digits.pop()

    if len(code) == 12:  # UPC-A
        total = sum(digits[i] * 3 if i % 2 == 0 else digits[i] for i in range(11))
    elif len(code) == 13:  # EAN-13
        total = sum(digits[i] * 3 if i % 2 == 1 else digits[i] for i in range(12))
    else:
        return False

    return (10 - (total % 10)) % 10 == check


def _get_valid_upc_codes(text: str) -> list[str]:
    codes = _extract_upc_ean(text)
    return sorted({code for code in codes if _is_valid_upc_ean(code)})


def _extract_pdf(pdf_path: str) -> dict[str, Any]:
    doc = fitz.open(pdf_path)
    full_text_parts: list[str] = []
    images: list[dict[str, Any]] = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_text = page.get_text("text")
        full_text_parts.append(page_text)
        page_images_found = False

        for img_index, img_info in enumerate(page.get_images(full=True)):
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            img_bytes = base_image.get("image")
            if not img_bytes:
                continue

            image_format = base_image.get("ext", "png")
            image = Image.open(BytesIO(img_bytes))
            ocr_text = pytesseract.image_to_string(image)
            upc_codes = _get_valid_upc_codes(ocr_text)

            image_id = f"p{page_index + 1}_i{img_index}"
            images.append(
                {
                    "image_id": image_id,
                    "page": page_index + 1,
                    "index": img_index,
                    "format": image_format,
                    "width": image.width,
                    "height": image.height,
                    "data_base64": base64.b64encode(img_bytes).decode("ascii"),
                    "ocr_text": ocr_text,
                    "source": "embedded",
                    "upc_codes": upc_codes,
                }
            )
            page_images_found = True

        if not page_images_found:
            page_bytes = _render_page_image(page)
            image = Image.open(BytesIO(page_bytes))
            ocr_text = pytesseract.image_to_string(image)
            upc_codes = _get_valid_upc_codes(ocr_text)
            image_id = f"p{page_index + 1}_page"
            images.append(
                {
                    "image_id": image_id,
                    "page": page_index + 1,
                    "index": 0,
                    "format": "png",
                    "width": image.width,
                    "height": image.height,
                    "data_base64": base64.b64encode(page_bytes).decode("ascii"),
                    "ocr_text": ocr_text,
                    "source": "page_render",
                    "note": "Page rendered for OCR; no embedded images found.",
                    "upc_codes": upc_codes,
                }
            )

    pdf_text = "".join(full_text_parts)
    pdf_text_upc_codes = _get_valid_upc_codes(pdf_text)
    all_ocr_text = "\n".join(image["ocr_text"] for image in images)
    ocr_upc_codes = _get_valid_upc_codes(all_ocr_text)
    upc_codes = sorted(set(pdf_text_upc_codes + ocr_upc_codes))

    return {
        "pdf_text": pdf_text,
        "images": images,
        "pdf_text_upc_codes": pdf_text_upc_codes,
        "upc_codes": upc_codes,
    }


@app.post("/extract")
async def extract_pdf(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        result = _extract_pdf(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    result["file_name"] = file.filename
    result["created_at"] = datetime.now(timezone.utc).isoformat()

    collection = _get_collection()
    if collection is not None:
        insert_result = collection.insert_one(result)
        result["id"] = str(insert_result.inserted_id)

    return result
