import os
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image


def _resolve_path(path_value: str) -> str:
    path = Path(path_value)
    if path.is_absolute():
        return str(path)
    return str((Path(__file__).resolve().parent / path).resolve())


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
    top_ratio = 0.0
    bottom_ratio = 1.0

    split_care_labels(
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


if __name__ == "__main__":
    main()
