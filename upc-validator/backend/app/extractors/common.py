import os
import re
import shutil
import subprocess
import tempfile
from typing import Iterable

import fitz  # PyMuPDF
from PIL import Image, ImageOps

try:
    import pytesseract
except Exception as exc:  # pragma: no cover - optional dependency
    print(f"pytesseract not found: {exc}")
    pytesseract = None


def normalize_text(text: str) -> str:
    text = re.sub(r"[^\x20-\x7E]", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)
    return text.strip()


def ocr_image(image: Image.Image) -> str:
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


def render_page_image(page: fitz.Page, zoom: float = 2.0) -> Image.Image:
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    mode = "RGBA" if pix.alpha else "RGB"
    return Image.frombytes(mode, [pix.width, pix.height], pix.samples)


def is_valid_upc_ean(code: str) -> bool:
    if not code.isdigit():
        return False
    digits = list(map(int, code))
    check = digits.pop()
    if len(code) == 12:  # UPC-A
        total = sum(digits[i] * 3 if i % 2 == 0 else digits[i] for i in range(11))
    elif len(code) == 13:  # EAN-13
        total = sum(digits[i] * 3 if i % 2 == 1 else digits[i] for i in range(12))
    else:
        return False
    return (10 - (total % 10)) % 10 == check


def extract_upc_candidate(text: str) -> str:
    normalized = normalize_text(text)
    match = re.search(r"(?:EAN\/?UPC|EAN|UPC)?\s*([0-9][0-9\s]{10,15})", normalized, re.IGNORECASE)
    if not match:
        return ""
    digits = re.sub(r"\s+", "", match.group(1))
    return digits if len(digits) in (12, 13) else ""


def extract_valid_upc(text: str) -> str:
    candidate = extract_upc_candidate(text)
    if not candidate:
        return ""
    return candidate if is_valid_upc_ean(candidate) else ""


def first_match(values: Iterable[str]) -> str:
    for value in values:
        if value:
            return value
    return ""
