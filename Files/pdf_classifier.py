import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageOps

try:
    import pytesseract
except Exception as exc:  # pragma: no cover - optional dependency
    print(f"pytesseract not found: {exc}")
    pytesseract = None


def _resolve_path(path_value: str) -> str:
    path = Path(path_value)
    if path.is_absolute():
        return str(path)
    return str((Path(__file__).resolve().parent / path).resolve())


def _normalize_text(text: str) -> str:
    text = re.sub(r"[^\x20-\x7E]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _ocr_image(image: Image.Image) -> str:
    gray = ImageOps.autocontrast(image.convert("L"))
    if pytesseract is not None:
        return pytesseract.image_to_string(gray, config="--psm 6")
    tesseract_bin = shutil.which("tesseract")
    if not tesseract_bin:
        return ""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "ocr_input.png")
        output_base = os.path.join(tmpdir, "ocr_output")
        gray.save(input_path, "PNG")
        try:
            subprocess.run(
                [tesseract_bin, input_path, output_base, "--psm", "6"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            return ""
        output_path = f"{output_base}.txt"
        try:
            with open(output_path, "r", encoding="utf-8") as handle:
                return handle.read()
        except FileNotFoundError:
            return ""


def classify_pdf(pdf_path: str) -> dict:
    """Classify a PDF as care label or RFID hang tag."""
    pdf_path = _resolve_path(pdf_path)
    doc = fitz.open(pdf_path)
    page = doc[0]
    text = page.get_text() or ""
    if len(text.strip()) < 20:
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        mode = "RGBA" if pix.alpha else "RGB"
        page_img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        text = f"{text}\n{_ocr_image(page_img)}"
    doc.close()

    normalized = _normalize_text(text)

    care_patterns = [
        r"\bRN#?\b",
        r"\bMade In\b",
        r"\bHecho En\b",
        r"Exclusive of Decoration",
        r"Body & Pocket",
        r"Inner Layer",
    ]
    rfid_patterns = [
        r"WALMART\.COM/AVIA",
        r"Find more at Walmart\.com",
        r"REGISTERED TRADEMARK",
        r"AVIA STRETCH",
        r"\bBLACK SOOT\b",
        r"\bSALSA DELIGHT\b",
    ]

    evidence = {"care_label": [], "rfid": []}
    care_score = 0
    rfid_score = 0

    for pattern in care_patterns:
        if re.search(pattern, normalized, re.IGNORECASE):
            evidence["care_label"].append(pattern)
            care_score += 1

    for pattern in rfid_patterns:
        if re.search(pattern, normalized, re.IGNORECASE):
            evidence["rfid"].append(pattern)
            rfid_score += 1

    if care_score == 0 and rfid_score == 0:
        label = "unknown"
    else:
        label = "care_label" if care_score >= rfid_score else "rfid"

    return {
        "type": label,
        "care_score": care_score,
        "rfid_score": rfid_score,
        "evidence": evidence,
    }


if __name__ == "__main__":
    import json

    result = classify_pdf("care label.pdf")
    print(json.dumps(result, indent=2))
