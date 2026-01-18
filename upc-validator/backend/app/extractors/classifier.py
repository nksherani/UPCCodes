import re
from typing import Any

import fitz  # PyMuPDF

from .common import normalize_text, ocr_image, render_page_image


def classify_pdf(pdf_path: str) -> dict[str, Any]:
    """Classify a PDF as care label or RFID hang tag."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    text = page.get_text() or ""
    if len(text.strip()) < 20:
        text = f"{text}\n{ocr_image(render_page_image(page))}"
    doc.close()

    normalized = normalize_text(text)

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
        r"\bBLACK\s+SOOT\b",
        r"\bSALSA\s+DELIGHT\b",
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
