import re
from typing import Any

import fitz  # PyMuPDF
from PIL import Image

try:
    from pyzbar.pyzbar import decode as zbar_decode
except Exception:  # pragma: no cover - optional dependency
    zbar_decode = None

from .common import (
    extract_upc_candidate,
    extract_valid_upc,
    normalize_text,
    ocr_image,
    render_page_image,
)


def _decode_barcodes(image: Image.Image) -> list[str]:
    if zbar_decode is None:
        return []
    decoded = zbar_decode(image)
    values: list[str] = []
    for item in decoded:
        try:
            value = item.data.decode("utf-8").strip()
        except Exception:
            continue
        if value:
            values.append(value)
    return values


def extract_parent_info(pdf_path: str) -> dict[str, Any]:
    doc = fitz.open(pdf_path)
    page = doc[0]
    text = page.get_text() or ""
    if len(text.strip()) < 20:
        text = f"{text}\n{ocr_image(render_page_image(page))}"
    parent_info: dict[str, Any] = {}

    if "STRETCH WOVEN DRESS" in text:
        parent_info["product_name"] = "Stretch Woven Dress"

    ref_match = re.search(r"Reference #:\s*([^\n]+)", text)
    if ref_match:
        parent_info["reference"] = ref_match.group(1).strip()

    job_match = re.search(r"Job #:\s*([^\n]+)", text)
    if job_match:
        parent_info["job_number"] = job_match.group(1).strip()

    style_match = re.search(r"Style #:\s*([^\n]+)", text)
    if style_match:
        parent_info["style_number"] = style_match.group(1).strip()

    po_match = re.search(r"PO #:\s*([^\n]+)", text)
    if po_match:
        parent_info["po_number"] = po_match.group(1).strip()

    date_match = re.search(r"Date:\s*([^\n]+)", text)
    if date_match:
        parent_info["date"] = date_match.group(1).strip()

    if "r-pac International Corporation" in text:
        parent_info["manufacturer"] = "r-pac International Corporation"
        parent_info["manufacturer_location"] = "Taiwan"

    normalized = normalize_text(text)
    color_match = re.search(r"\b(BLACK\s+SOOT|SALSA\s+DELIGHT)\b", normalized, re.IGNORECASE)
    if color_match:
        parent_info["color"] = color_match.group(1).upper().replace("  ", " ")

    doc.close()
    return parent_info


def extract_tag_info(text: str, tag_image: Image.Image | None = None) -> dict[str, Any]:
    info: dict[str, Any] = {}
    normalized = normalize_text(text)

    size_match = re.search(r"\b(XXXL|XXL|XL|L|M|S|XS)\b\s*\(([^)]+)\)", normalized)
    if size_match:
        info["size"] = size_match.group(1)
        info["size_range"] = size_match.group(2)

    upc = extract_valid_upc(normalized)
    if upc:
        info["upc"] = upc
    else:
        candidate = extract_upc_candidate(normalized)
        if candidate:
            info["upc_candidate"] = candidate

    if tag_image is not None:
        barcodes = _decode_barcodes(tag_image)
        if barcodes:
            info["barcode"] = barcodes[0]

    color_match = re.search(r"(BLACK\s+SOOT|SALSA\s+DELIGHT)", normalized, re.IGNORECASE)
    if color_match:
        info["color"] = color_match.group(1).upper().replace("  ", " ")

    color_code_match = re.search(r"(BLACK\s+SOOT|SALSA\s+DELIGHT)\s+(\d+)", normalized, re.IGNORECASE)
    if color_code_match:
        info["color_code"] = color_code_match.group(2)

    style_match = re.search(r"(AV\d+[A-Z]+\d+)", normalized)
    if style_match:
        info["style_number"] = style_match.group(1)

    rn_match = re.search(r"RN#\s*(\d+)", normalized)
    if rn_match:
        info["rn_number"] = rn_match.group(1)

    return info


def extract_hang_tags(
    pdf_path: str,
    columns: int = 8,
    skip_first_column: bool = True,
    top_ratio: float = 0.22,
    bottom_ratio: float = 0.92,
    zoom: float = 3.0,
) -> dict[str, Any]:
    doc = fitz.open(pdf_path)
    hang_tags: list[dict[str, Any]] = []

    for page_num, page in enumerate(doc):
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        mat = fitz.Matrix(zoom, zoom)
        column_width = page_width / columns
        start_index = 1 if skip_first_column else 0

        top_y = page_height * top_ratio
        bottom_y = page_height * bottom_ratio

        for i in range(start_index, columns):
            x0 = i * column_width
            x1 = (i + 1) * column_width
            clip_rect = fitz.Rect(x0, top_y, x1, bottom_y)

            pix = page.get_pixmap(matrix=mat, clip=clip_rect)
            mode = "RGBA" if pix.alpha else "RGB"
            tag_img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

            tag_text = page.get_text("text", clip=clip_rect) or ""
            ocr_text = ocr_image(tag_img) if len(tag_text.strip()) < 20 else ""
            combined_text = "\n".join(part for part in [tag_text, ocr_text] if part.strip())
            tag_info = extract_tag_info(combined_text, tag_img)

            tag_info["page"] = page_num + 1
            tag_info["position"] = i
            hang_tags.append(tag_info)

    doc.close()
    parent_info = extract_parent_info(pdf_path)
    return {"parent_info": parent_info, "hang_tags": hang_tags}
