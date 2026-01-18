import re
from typing import Any

import pandas as pd


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text).upper()


def _normalize_upc(value: Any) -> str:
    if value is None:
        return ""
    digits = re.sub(r"\D", "", str(value))
    return digits


def _normalize_column_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _map_columns(columns: list[str]) -> dict[str, str]:
    normalized = {_normalize_column_name(col): col for col in columns}

    def find_column(*candidates: str) -> str:
        for key, original in normalized.items():
            for candidate in candidates:
                if candidate in key:
                    return original
        return ""

    return {
        "style": find_column("style"),
        "size": find_column("size"),
        "color": find_column("color"),
        "care_upc": find_column("carelabelupc", "careupc", "carelabel", "careupc"),
        "hang_upc": find_column("hangtagupc", "hangupc", "rfidupc", "hangtag", "rfid"),
        "upc": find_column("upc"),
    }


def read_spreadsheet(file_path: str) -> list[dict[str, Any]]:
    df = pd.read_excel(file_path)
    column_map = _map_columns(df.columns.tolist())
    rows: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        style = _normalize_value(row.get(column_map["style"])) if column_map["style"] else ""
        size = _normalize_value(row.get(column_map["size"])) if column_map["size"] else ""
        color = _normalize_value(row.get(column_map["color"])) if column_map["color"] else ""
        care_upc = _normalize_upc(row.get(column_map["care_upc"])) if column_map["care_upc"] else ""
        hang_upc = _normalize_upc(row.get(column_map["hang_upc"])) if column_map["hang_upc"] else ""
        generic_upc = _normalize_upc(row.get(column_map["upc"])) if column_map["upc"] else ""

        if not care_upc and generic_upc:
            care_upc = generic_upc

        rows.append(
            {
                "style": style,
                "size": size,
                "color": color,
                "care_upc": care_upc,
                "hang_upc": hang_upc,
            }
        )

    return rows


def _match_item(items: list[dict[str, Any]], style: str, size: str, color: str) -> tuple[dict[str, Any] | None, str]:
    if not items:
        return None, "none"

    def normalize_item(item: dict[str, Any]) -> dict[str, str]:
        return {
            "style": _normalize_value(item.get("style_number")),
            "size": _normalize_value(item.get("size")),
            "color": _normalize_value(item.get("color")),
        }

    normalized_items = [(item, normalize_item(item)) for item in items]

    for item, norm in normalized_items:
        if norm["style"] == style and norm["size"] == size and norm["color"] == color and style:
            return item, "style+size+color"

    for item, norm in normalized_items:
        if norm["style"] == style and norm["size"] == size and style:
            return item, "style+size"

    for item, norm in normalized_items:
        if norm["style"] == style and norm["color"] == color and style:
            return item, "style+color"

    for item, norm in normalized_items:
        if norm["style"] == style and style:
            return item, "style"

    return None, "none"


def validate_rows(
    rows: list[dict[str, Any]],
    care_labels: list[dict[str, Any]],
    hang_tags: list[dict[str, Any]],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []

    for row in rows:
        style = _normalize_value(row.get("style"))
        size = _normalize_value(row.get("size"))
        color = _normalize_value(row.get("color"))

        care_item, care_match = _match_item(care_labels, style, size, color)
        hang_item, hang_match = _match_item(hang_tags, style, size, color)

        care_upc_expected = _normalize_upc(row.get("care_upc"))
        hang_upc_expected = _normalize_upc(row.get("hang_upc"))
        care_upc_actual = _normalize_upc(care_item.get("upc") if care_item else "")
        hang_upc_actual = _normalize_upc(hang_item.get("upc") if hang_item else "")

        results.append(
            {
                "row": row,
                "care_label": {
                    "match": care_match,
                    "upc_expected": care_upc_expected,
                    "upc_actual": care_upc_actual,
                    "upc_matches": bool(care_upc_expected and care_upc_actual and care_upc_expected == care_upc_actual),
                    "item": care_item,
                },
                "hang_tag": {
                    "match": hang_match,
                    "upc_expected": hang_upc_expected,
                    "upc_actual": hang_upc_actual,
                    "upc_matches": bool(hang_upc_expected and hang_upc_actual and hang_upc_expected == hang_upc_actual),
                    "item": hang_item,
                },
            }
        )

    summary = {
        "rows": len(results),
        "care_label_matches": sum(1 for item in results if item["care_label"]["upc_matches"]),
        "hang_tag_matches": sum(1 for item in results if item["hang_tag"]["upc_matches"]),
    }

    return {"summary": summary, "results": results}
