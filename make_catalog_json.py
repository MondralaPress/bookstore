import json
import math
from pathlib import Path

import pandas as pd


INPUT_XLSX = "Catalog.xlsx"
OUTPUT_JSON = "catalog.json"


def normalize_colname(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_")


def is_nan(v) -> bool:
    return isinstance(v, float) and math.isnan(v)


def clean_text(v):
    if v is None or is_nan(v) or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, str):
        v = v.strip()
        return v if v else None
    return v


def digits_only(v):
    v = clean_text(v)
    if v is None:
        return None
    s = "".join(ch for ch in str(v) if ch.isdigit())
    return s if s else None


def yes_no(v):
    v = clean_text(v)
    if v is None:
        return None
    if isinstance(v, str) and v.lower() in {"yes", "true", "1", "y"}:
        return "yes"
    return None


def to_number(v):
    v = clean_text(v)
    if v is None:
        return None
    try:
        num = float(v)
        if math.isnan(num):
            return None
        return int(num) if num.is_integer() else num
    except Exception:
        return None


def normalize_cover(v):
    v = clean_text(v)
    if v is None:
        return None
    v = str(v).strip().replace("\\", "/")
    if "/" not in v and not v.startswith("covers"):
        return f"covers/{v}"
    return v


def sanitize_record(record: dict) -> dict:
    """Convert any lingering NaN to None, then drop None keys."""
    out = {}
    for k, v in record.items():
        if v is None or is_nan(v) or (isinstance(v, float) and pd.isna(v)):
            continue
        out[k] = v
    return out


def main():
    cwd = Path.cwd()
    xlsx_path = cwd / INPUT_XLSX
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Cannot find '{INPUT_XLSX}' in {cwd}")

    df = pd.read_excel(xlsx_path)
    df.columns = [normalize_colname(c) for c in df.columns]

    # Force pandas NA -> None as much as possible
    df = df.where(pd.notnull(df), None)

    # Export only active=yes if present
    if "active" in df.columns:
        df["active"] = df["active"].apply(yes_no)
        df = df[df["active"] == "yes"]

    # Text fields
    text_fields = [
        "id", "title", "author", "translator", "publisher", "format",
        "shelf", "category", "series", "tags", "language_original",
        "description_short", "description_long", "supplier", "metadata_source"
    ]
    for col in text_fields:
        if col in df.columns:
            df[col] = df[col].apply(clean_text)

    # ISBN
    if "isbn" in df.columns:
        df["isbn"] = df["isbn"].apply(digits_only)

    # Featured
    if "featured" in df.columns:
        df["featured"] = df["featured"].apply(yes_no)

    # Numbers
    numeric_fields = [
        "pages", "series_number", "display_order", "shelf_order",
        "price_eur", "price_usd", "price_gbp", "year"
    ]
    for col in numeric_fields:
        if col in df.columns:
            df[col] = df[col].apply(to_number)

    # Cover
    if "cover" in df.columns:
        df["cover"] = df["cover"].apply(normalize_cover)

    records = df.to_dict(orient="records")
    cleaned = [sanitize_record(r) for r in records]

    out_path = cwd / OUTPUT_JSON
    with open(out_path, "w", encoding="utf-8") as f:
        # allow_nan=False ensures we NEVER write NaN again
        json.dump(cleaned, f, ensure_ascii=False, indent=2, allow_nan=False)

    print(f"Wrote '{OUTPUT_JSON}' with {len(cleaned)} books.")


if __name__ == "__main__":
    main()