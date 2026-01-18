import json
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
    text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)
    return text.strip()


def _is_valid_upc_ean(code: str) -> bool:
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


def _extract_upc_ean(text: str) -> str:
    normalized = _normalize_text(text)
    match = re.search(r"(?:EAN\/?UPC|EAN|UPC)?\s*([0-9][0-9\s]{10,15})", normalized, re.IGNORECASE)
    if not match:
        return ""
    digits = re.sub(r"\s+", "", match.group(1))
    if len(digits) not in (12, 13):
        return ""
    return digits if _is_valid_upc_ean(digits) else ""


def _extract_upc_candidate(text: str) -> str:
    normalized = _normalize_text(text)
    match = re.search(r"(?:EAN\/?UPC|EAN|UPC)?\s*([0-9][0-9\s]{10,15})", normalized, re.IGNORECASE)
    if not match:
        return ""
    digits = re.sub(r"\s+", "", match.group(1))
    return digits if len(digits) in (12, 13) else ""


def _ocr_image(image: Image.Image) -> str:
    gray = ImageOps.autocontrast(image.convert("L"))
    if pytesseract is not None:
        return pytesseract.image_to_string(gray, config="--psm 6")
    tesseract_bin = shutil.which("tesseract")
    if not tesseract_bin:
        print("tesseract not available; OCR skipped")
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
        except subprocess.CalledProcessError as exc:
            print(f"tesseract failed: {exc.stderr.strip()}")
            return ""
        output_path = f"{output_base}.txt"
        try:
            with open(output_path, "r", encoding="utf-8") as handle:
                return handle.read()
        except FileNotFoundError:
            return ""


def extract_parent_info(pdf_path: str) -> dict:
    """Extract parent/header info from the PDF."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    text = page.get_text() or ""
    if not text.strip():
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        mode = "RGBA" if pix.alpha else "RGB"
        page_img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        text = _ocr_image(page_img)
    parent_info: dict = {}
    normalized = _normalize_text(text)

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

    color_match = re.search(r"\b(BLACK\s+SOOT|BLAC\s+SOOT)\b", normalized, re.IGNORECASE)
    if color_match:
        parent_info["color"] = "BLACK SOOT"

    doc.close()
    return parent_info


def _extract_size(normalized: str) -> tuple[str, str]:
    size_match = re.search(r"\b(XXXL|XXL|XL|L|M|S|XS)\b", normalized)
    size_range = ""
    if size_match:
        range_match = re.search(rf"{size_match.group(1)}\s*\(([^)]+)\)", normalized)
        if range_match:
            size_range = range_match.group(1)
        return size_match.group(1), size_range
    return "", ""


def _extract_country(text: str) -> str:
    match = re.search(r"(?:Made In|Hecho En)\s+([A-Za-z ]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_composition(text: str) -> list[dict]:
    compositions: list[dict] = []
    for match in re.finditer(r"(\d{1,3})%\s*([A-Za-z][A-Za-z\s/&-]+)", text):
        pct = int(match.group(1))
        material = " ".join(match.group(2).split()).strip(" .;/")
        if material:
            compositions.append({"percent": pct, "material": material})
    return compositions


def extract_care_label_info(text: str) -> dict:
    info: dict = {}
    normalized = _normalize_text(text)

    size, size_range = _extract_size(normalized)
    if size:
        info["size"] = size
    if size_range:
        info["size_range"] = size_range

    rn_match = re.search(r"RN#?\s*(\d+)", normalized)
    if rn_match:
        info["rn_number"] = rn_match.group(1)

    upc = _extract_upc_ean(normalized)
    if upc:
        info["upc"] = upc
    elif normalized:
        candidate = _extract_upc_candidate(normalized)
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


def split_care_labels(
    pdf_path: str,
    output_dir: str,
    columns: int = 8,
    skip_first_column: bool = True,
    zoom: float = 3.0,
    column_width: float | None = None,
    left_offset: float = 0.0,
    top_ratio: float = 0.0,
    bottom_ratio: float = 1.0,
) -> list[str]:
    """Split each PDF page into column label images."""
    os.makedirs(output_dir, exist_ok=True)
    output_paths: list[str] = []

    doc = fitz.open(pdf_path)
    mat = fitz.Matrix(zoom, zoom)

    for page_num, page in enumerate(doc):
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        column_width = column_width or (page_width / columns)

        top_y = page_height * top_ratio
        bottom_y = page_height * bottom_ratio
        start_index = 1 if skip_first_column else 0

        for i in range(start_index, columns):
            x0 = left_offset + (i * column_width)
            x1 = left_offset + ((i + 1) * column_width)
            x0 = max(0.0, min(page_width, x0))
            x1 = max(0.0, min(page_width, x1))
            if x1 <= x0:
                continue
            clip_rect = fitz.Rect(x0, top_y, x1, bottom_y)

            pix = page.get_pixmap(matrix=mat, clip=clip_rect)
            mode = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

            label_index = i if skip_first_column else i + 1
            filename = f"page{page_num + 1}_label{label_index}.png"
            filepath = os.path.join(output_dir, filename)
            img.save(filepath, "PNG")
            output_paths.append(filepath)

            print(f"Saved {filepath}")

    doc.close()
    return output_paths


def extract_care_labels(
    pdf_path: str,
    output_dir: str,
    columns: int = 8,
    skip_first_column: bool = True,
    zoom: float = 3.0,
    column_width: float | None = None,
    left_offset: float = 0.0,
    top_ratio: float = 0.0,
    bottom_ratio: float = 1.0,
) -> list[dict]:
    """Extract care labels as images and metadata."""
    os.makedirs(output_dir, exist_ok=True)
    labels: list[dict] = []

    doc = fitz.open(pdf_path)
    mat = fitz.Matrix(zoom, zoom)

    for page_num, page in enumerate(doc):
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        column_width = column_width or (page_width / columns)

        top_y = page_height * top_ratio
        bottom_y = page_height * bottom_ratio
        start_index = 1 if skip_first_column else 0

        for i in range(start_index, columns):
            x0 = left_offset + (i * column_width)
            x1 = left_offset + ((i + 1) * column_width)
            x0 = max(0.0, min(page_width, x0))
            x1 = max(0.0, min(page_width, x1))
            if x1 <= x0:
                continue
            clip_rect = fitz.Rect(x0, top_y, x1, bottom_y)

            pix = page.get_pixmap(matrix=mat, clip=clip_rect)
            mode = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)

            label_index = i if skip_first_column else i + 1
            filename = f"page{page_num + 1}_label{label_index}.png"
            filepath = os.path.join(output_dir, filename)
            img.save(filepath, "PNG")

            label_text = page.get_text("text", clip=clip_rect) or ""
            ocr_text = ""
            if len(label_text.strip()) < 20:
                ocr_text = _ocr_image(img)
            combined_text = "\n".join(part for part in [label_text, ocr_text] if part.strip())
            label_info = extract_care_label_info(combined_text)
            label_info["image_path"] = filepath
            label_info["page"] = page_num + 1
            label_info["position"] = i
            labels.append(label_info)

            print(f"Saved {filepath}")

    doc.close()
    return labels


def main() -> None:
    # Adjust these values to experiment with the crop grid.
    pdf_path = _resolve_path("care label.pdf")
    output_dir = _resolve_path("care_labels")
    columns = 8
    include_first_column = False
    zoom = 3.0
    # Set a custom column width (points/pixels at 72 dpi), or None to auto-calc.
    column_width = 88
    # Shift the full grid from the left edge (points/pixels at 72 dpi).
    left_offset = 55
    top_ratio = 0.22
    bottom_ratio = 0.61
    parent_info = extract_parent_info(pdf_path)
    labels = extract_care_labels(
        pdf_path=pdf_path,
        output_dir=output_dir,
        columns=columns,
        skip_first_column=not include_first_column,
        zoom=zoom,
        column_width=column_width,
        left_offset=left_offset,
        top_ratio=top_ratio,
        bottom_ratio=bottom_ratio,
    )

    result = {
        "parent_info": parent_info,
        "care_labels": labels,
    }

    json_path = os.path.join(output_dir, "metadata.json")
    with open(json_path, "w") as handle:
        json.dump(result, handle, indent=2)

    print(f"\n✓ Extracted {len(labels)} care labels")
    print(f"✓ Saved metadata to: {json_path}")
    print(f"✓ Images saved to: {output_dir}/")


if __name__ == "__main__":
    main()
