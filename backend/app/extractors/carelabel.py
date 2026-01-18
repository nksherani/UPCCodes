import os
import re
from typing import Any

import fitz  # PyMuPDF
from PIL import Image

from .common import (
    extract_upc_candidate,
    extract_valid_upc,
    normalize_text,
    ocr_image,
    render_page_image,
)


def _extract_size(normalized: str) -> tuple[str, str]:
    size_match = re.search(r"\b(XXXL|XXL|XL|L|M|S|XS)\b", normalized)
    size_range = ""
    if size_match:
        range_match = re.search(rf"{size_match.group(1)}\s*\(([^)]+)\)", normalized)
        if range_match:
            size_range = range_match.group(1)
        return size_match.group(1), size_range
    range_match = re.search(r"\b(\d{1,2}\s*-\s*\d{1,2}|\d{1,2})\b", normalized)
    if range_match:
        size_range = range_match.group(1).replace(" ", "")
        range_map = {
            "0-2": "XS",
            "4-6": "S",
            "8-10": "M",
            "12-14": "L",
            "16-18": "XL",
            "20": "XXL",
            "22": "XXXL",
        }
        return range_map.get(size_range, ""), size_range
    return "", ""


def _extract_country(text: str) -> str:
    match = re.search(r"(?:Made In|Hecho En)\s+([A-Za-z ]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_composition(text: str) -> list[dict[str, Any]]:
    compositions: list[dict[str, Any]] = []
    for match in re.finditer(r"(\d{1,3})%\s*([A-Za-z][A-Za-z\s/&-]+)", text):
        pct = int(match.group(1))
        material = " ".join(match.group(2).split()).strip(" .;/")
        if material:
            compositions.append({"percent": pct, "material": material})
    return compositions


def extract_parent_info(pdf_path: str) -> dict[str, Any]:
    doc = fitz.open(pdf_path)
    page = doc[0]
    text = page.get_text() or ""
    if len(text.strip()) < 20:
        text = f"{text}\n{ocr_image(render_page_image(page))}"
    parent_info: dict[str, Any] = {}
    normalized = normalize_text(text)

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

    color_match = re.search(r"\b(BLACK\s+SOOT|BLAC\s+SOOT|SALSA\s+DELIGHT)\b", normalized, re.IGNORECASE)
    if color_match:
        parent_info["color"] = color_match.group(1).upper().replace("  ", " ")

    doc.close()
    return parent_info


def extract_care_label_info(text: str) -> dict[str, Any]:
    info: dict[str, Any] = {}
    normalized = normalize_text(text)

    size, size_range = _extract_size(normalized)
    if size:
        info["size"] = size
    if size_range:
        info["size_range"] = size_range

    rn_match = re.search(r"RN#?\s*(\d+)", normalized)
    if rn_match:
        info["rn_number"] = rn_match.group(1)

    upc = extract_valid_upc(normalized)
    if upc:
        info["upc"] = upc
    else:
        candidate = extract_upc_candidate(normalized)
        if candidate:
            info["upc_candidate"] = candidate

    country = _extract_country(text)
    if country:
        info["country_of_origin"] = country

    compositions = _extract_composition(text)
    if compositions:
        info["composition"] = compositions

    if re.search(r"Exclusive of Decoration", text, re.IGNORECASE):
        info["exclusive_of_decoration"] = True

    style_match = re.search(r"\b(AV[A-Z0-9]+)\b", normalized)
    if style_match:
        info["style_number"] = style_match.group(1)

    return info


def extract_care_labels(
    pdf_path: str,
    columns: int = 8,
    skip_first_column: bool = True,
    zoom: float = 3.0,
    column_width: float = 88.0,
    left_offset: float = 45.0,
    top_ratio: float = 0.22,
    bottom_ratio: float = 0.61,
) -> dict[str, Any]:
    doc = fitz.open(pdf_path)
    mat = fitz.Matrix(zoom, zoom)
    labels: list[dict[str, Any]] = []

    for page_num, page in enumerate(doc):
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        col_width = column_width or (page_width / columns)

        top_y = page_height * top_ratio
        bottom_y = page_height * bottom_ratio
        start_index = 1 if skip_first_column else 0

        for i in range(start_index, columns):
            x0 = left_offset + (i * col_width)
            x1 = left_offset + ((i + 1) * col_width)
            x0 = max(0.0, min(page_width, x0))
            x1 = max(0.0, min(page_width, x1))
            if x1 <= x0:
                continue
            clip_rect = fitz.Rect(x0, top_y, x1, bottom_y)

            pix = page.get_pixmap(matrix=mat, clip=clip_rect)
            mode = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

            label_text = page.get_text("text", clip=clip_rect) or ""
            ocr_text = ocr_image(img) if len(label_text.strip()) < 20 else ""
            combined_text = "\n".join(part for part in [label_text, ocr_text] if part.strip())

            label_info = extract_care_label_info(combined_text)
            label_info["page"] = page_num + 1
            label_info["position"] = i
            labels.append(label_info)

    doc.close()
    parent_info = extract_parent_info(pdf_path)
    return {"parent_info": parent_info, "care_labels": labels}
