import json
import os
import re
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

def _resolve_path(path_value: str) -> str:
    path = Path(path_value)
    if path.is_absolute():
        return str(path)
    return str((Path(__file__).resolve().parent / path).resolve())


def _normalize_text(text: str) -> str:
    text = re.sub(r"[^\x20-\x7E]", " ", text)
    text = re.sub(r"(\d)\s+(\d)", r"\1\2", text)
    return text


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


def _extract_upc_ean(text: str) -> str:
    normalized = _normalize_text(text)
    match = re.search(r"(?:EAN\/?UPC|EANIUPC)?\s*(\d{12,13})", normalized, re.IGNORECASE)
    if not match:
        return ""
    code = match.group(1)
    return code if _is_valid_upc_ean(code) else ""


def extract_parent_info(pdf_path):
    """Extract parent/header information from the PDF"""
    doc = fitz.open(pdf_path)
    page = doc[0]
    text = page.get_text()
    
    parent_info = {}
    
    # Extract product description
    if "STRETCH WOVEN DRESS" in text:
        parent_info['product_name'] = "Stretch Woven Dress"
    
    # Extract reference and job numbers
    ref_match = re.search(r'Reference #:\s*([^\n]+)', text)
    if ref_match:
        parent_info['reference'] = ref_match.group(1).strip()
    
    job_match = re.search(r'Job #:\s*([^\n]+)', text)
    if job_match:
        parent_info['job_number'] = job_match.group(1).strip()
    
    # Extract style number
    style_match = re.search(r'Style #:\s*([^\n]+)', text)
    if style_match:
        parent_info['style_number'] = style_match.group(1).strip()
    
    # Extract PO number
    po_match = re.search(r'PO #:\s*([^\n]+)', text)
    if po_match:
        parent_info['po_number'] = po_match.group(1).strip()
    
    # Extract date
    date_match = re.search(r'Date:\s*([^\n]+)', text)
    if date_match:
        parent_info['date'] = date_match.group(1).strip()
    
    # Extract manufacturer info
    if "r-pac International Corporation" in text:
        parent_info['manufacturer'] = "r-pac International Corporation"
        parent_info['manufacturer_location'] = "Taiwan"
    
    doc.close()
    return parent_info

def _crop_white_label(
    image: Image.Image,
    threshold: int = 235,
    row_ratio: float = 0.35,
    col_ratio: float = 0.35,
) -> Image.Image:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()

    white_mask = [[False] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if r >= threshold and g >= threshold and b >= threshold:
                white_mask[y][x] = True

    row_hits = [sum(1 for x in range(width) if white_mask[y][x]) for y in range(height)]
    row_threshold = int(width * row_ratio)
    candidate_rows = [y for y, count in enumerate(row_hits) if count >= row_threshold]

    if not candidate_rows:
        return image

    best_start = best_end = 0
    start = prev = candidate_rows[0]
    for y in candidate_rows[1:]:
        if y == prev + 1:
            prev = y
            continue
        if (prev - start) > (best_end - best_start):
            best_start, best_end = start, prev
        start = prev = y
    if (prev - start) > (best_end - best_start):
        best_start, best_end = start, prev

    row_top = best_start
    row_bottom = best_end
    row_height = max(1, row_bottom - row_top + 1)

    col_hits = []
    for x in range(width):
        count = 0
        for y in range(row_top, row_bottom + 1):
            if white_mask[y][x]:
                count += 1
        col_hits.append(count)

    col_threshold = int(row_height * col_ratio)
    candidate_cols = [x for x, count in enumerate(col_hits) if count >= col_threshold]
    if not candidate_cols:
        return image

    col_left = candidate_cols[0]
    col_right = candidate_cols[-1]

    pad = max(3, int(min(width, height) * 0.01))
    left = max(0, col_left - pad)
    top = max(0, row_top - pad)
    right = min(width, col_right + pad)
    bottom = min(height, row_bottom + pad)

    if right <= left or bottom <= top:
        return image

    return image.crop((left, top, right, bottom))


def _find_label_rect(page: fitz.Page, clip_rect: fitz.Rect) -> fitz.Rect | None:
    blocks = page.get_text("blocks", clip=clip_rect)
    selected = []

    for block in blocks:
        text = (block[4] or "").strip()
        if not text:
            continue
        text_line = " ".join(text.split())
        if "REGISTERED TRADEMARK" in text_line:
            continue
        if text_line == "WALMART.COM/AVIA":
            continue

        if (
            re.search(r"\b(XXXL|XXL|XL|L|M|S|XS)\b", text_line)
            or "Find more at Walmart.com" in text_line
            or "AVIA STRETCH" in text_line
            or "BLACK SOOT" in text_line
            or re.search(r"\bAV\d", text_line)
        ):
            selected.append(block)

    if not selected:
        return None

    min_x = min(b[0] for b in selected)
    min_y = min(b[1] for b in selected)
    max_x = max(b[2] for b in selected)
    max_y = max(b[3] for b in selected)

    pad = 6
    return fitz.Rect(
        max(clip_rect.x0, min_x - pad),
        max(clip_rect.y0, min_y - pad),
        min(clip_rect.x1, max_x + pad),
        min(clip_rect.y1, max_y + pad),
    )


def crop_hang_tags(
    pdf_path,
    output_dir='hang_tags',
    columns=8,
    skip_first_column=True,
    top_ratio=0.22,
    bottom_ratio=0.92,
    zoom=3,
    crop_to_label=True,
    label_threshold=235,
    label_row_ratio=0.35,
    label_col_ratio=0.35,
    label_mode="text",
):
    """Crop individual hang tags from PDF pages as images"""
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    hang_tags = []
    
    # Process each page
    for page_num, page in enumerate(doc):
        # Get page dimensions
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        
        print(f"Page {page_num}: {page_width} x {page_height} points")
        
        # Render and crop each column tag from the page
        mat = fitz.Matrix(zoom, zoom)
        column_width = page_width / columns
        start_index = 1 if skip_first_column else 0

        top_y = page_height * top_ratio
        bottom_y = page_height * bottom_ratio

        for i in range(start_index, columns):
            x0 = i * column_width
            x1 = (i + 1) * column_width
            clip_rect = fitz.Rect(x0, top_y, x1, bottom_y)

            try:
                label_rect = None
                if crop_to_label and label_mode == "text":
                    label_rect = _find_label_rect(page, clip_rect)

                render_rect = label_rect or clip_rect
                pix = page.get_pixmap(matrix=mat, clip=render_rect)
                mode = "RGBA" if pix.alpha else "RGB"
                tag_img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                if crop_to_label and label_mode == "white":
                    tag_img = _crop_white_label(
                        tag_img,
                        threshold=label_threshold,
                        row_ratio=label_row_ratio,
                        col_ratio=label_col_ratio,
                    )

                tag_text = page.get_text("text", clip=render_rect)
                tag_info = extract_tag_info(tag_text)

                size = tag_info.get('size', f'tag{i}')
                color = tag_info.get('color', '').replace(' ', '_') or "unknown"
                filename = f"page{page_num}_col{i}_{size}_{color}.png"
                filepath = os.path.join(output_dir, filename)
                tag_img.save(filepath, 'PNG')

                tag_info['image_path'] = filepath
                tag_info['page'] = page_num
                tag_info['position'] = i
                hang_tags.append(tag_info)

                print(f"Saved: {filename}")
            except Exception as e:
                print(f"Error cropping tag column {i} on page {page_num}: {e}")
    
    doc.close()
    return hang_tags

def extract_tag_info(text):
    """Extract information from individual hang tag text"""
    info = {}
    normalized = _normalize_text(text)
    
    # Extract size
    size_match = re.search(r'\b(XXXL|XXL|XL|L|M|S|XS)\b\s*\(([^)]+)\)', normalized)
    if size_match:
        info['size'] = size_match.group(1)
        info['size_range'] = size_match.group(2)
    
    # Extract UPC
    upc = _extract_upc_ean(normalized)
    if upc:
        info['upc'] = upc
    
    # Extract color
    color_match = re.search(r'(BLACK SOOT|SALSA DELIGHT)', normalized)
    if color_match:
        info['color'] = color_match.group(1)
    
    # Extract color code
    color_code_match = re.search(r'(BLACK SOOT|SALSA DELIGHT)\s+(\d+)', normalized)
    if color_code_match:
        info['color_code'] = color_code_match.group(2)
    
    # Extract style number
    style_match = re.search(r'(AV\d+[A-Z]+\d+)', normalized)
    if style_match:
        info['style_number'] = style_match.group(1)
    
    # Extract RN number
    rn_match = re.search(r'RN#\s*(\d+)', normalized)
    if rn_match:
        info['rn_number'] = rn_match.group(1)
    
    return info

def main(pdf_path, output_dir='hang_tags'):
    """Main function to extract parent info and hang tag images"""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    print("=" * 60)
    print("EXTRACTING PARENT INFORMATION")
    print("=" * 60)
    
    # Extract parent information
    parent_info = extract_parent_info(pdf_path)
    print(json.dumps(parent_info, indent=2))
    
    print("\n" + "=" * 60)
    print("EXTRACTING HANG TAG IMAGES")
    print("=" * 60)
    
    # Extract hang tag images
    hang_tags = crop_hang_tags(pdf_path, output_dir)
    
    # Combine parent info with hang tags
    result = {
        'parent_info': parent_info,
        'hang_tags': hang_tags
    }
    
    # Save to JSON
    json_path = os.path.join(output_dir, 'metadata.json')
    with open(json_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n✓ Extracted {len(hang_tags)} hang tags")
    print(f"✓ Saved metadata to: {json_path}")
    print(f"✓ Images saved to: {output_dir}/")
    
    return result

# Usage
if __name__ == "__main__":
    pdf_path = _resolve_path("rfid.pdf")
    output_dir = _resolve_path("hang_tags")
    result = main(pdf_path, output_dir)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Product: {result['parent_info'].get('product_name')}")
    print(f"Total hang tags: {len(result['hang_tags'])}")
    print("\nHang tags by size:")
    for tag in result['hang_tags']:
        print(f"  - {tag.get('size', 'N/A'):5s} | {tag.get('color', 'N/A'):15s} | UPC: {tag.get('upc', 'N/A')}")