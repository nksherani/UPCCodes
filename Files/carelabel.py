import json
import re
import pdfplumber

def extract_care_labels_v2(pdf_path):
    # Regex refined for the specific format in your file
    # Matches 'EAN/UPC' followed by exactly 12 digits
    UPC_RE = re.compile(r"1\d{11}") 
    STYLE_RE = re.compile(r"Style\s*([A-Z0-9]+)")

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        full_text = page.extract_text()

        data = {
            "page": 1,
            "parent_information": {
                "style": STYLE_RE.search(full_text).group(1) if STYLE_RE.search(full_text) else None,
                "rn": "52469", # Found at source [144]
            },
            "products": []
        }

        # Divide by 8 columns (1 instruction + 7 sizes)
        # Source [111, 112] shows specific widths
        col_width = page.width / 8

        for i in range(1, 8):
            bbox = (i * col_width, page.height * 0.7, (i + 1) * col_width, page.height * 0.98)
            # Use crop for a hard boundary
            crop = page.crop(bbox)
            
            # Use x_tolerance=2 to keep the UPC digits from merging with nearby text
            text = crop.extract_text(x_tolerance=2) or ""
            
            if text:
                # Find the 12-digit UPC starting with 1
                upc_match = UPC_RE.search(text.replace(" ", ""))
                upc = upc_match.group(0) if upc_match else ""
                
                # The size is typically the last line in this specific box [cite: 147, 161, 174]
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                size = lines[-1] if lines else ""

                data["products"].append({
                    "upc": upc,
                    "size": size
                })

        return json.dumps([data], indent=2)

print(extract_care_labels_v2("care label.pdf"))