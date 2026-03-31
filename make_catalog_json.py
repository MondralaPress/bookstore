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


def split_semicolon_list(v):
    v = clean_text(v)
    if v is None:
        return None
    items = [item.strip() for item in str(v).split(";") if item.strip()]
    return items or None


def sanitize_record(record: dict) -> dict:
    """Convert lingering NaN to None, recurse into lists/dicts, then drop empty keys."""
    out = {}

    for k, v in record.items():
        if v is None or is_nan(v) or (isinstance(v, float) and pd.isna(v)):
            continue

        if isinstance(v, dict):
            v = sanitize_record(v)
            if not v:
                continue

        elif isinstance(v, list):
            cleaned_list = []
            for item in v:
                if item is None or is_nan(item) or (isinstance(item, float) and pd.isna(item)):
                    continue
                if isinstance(item, dict):
                    item = sanitize_record(item)
                    if item:
                        cleaned_list.append(item)
                else:
                    cleaned_list.append(item)
            if not cleaned_list:
                continue
            v = cleaned_list

        out[k] = v

    return out


def build_praise(row: dict) -> list:
    praise = []

    q1 = clean_text(row.get("praise_1_quote"))
    s1 = clean_text(row.get("praise_1_source"))
    if q1 or s1:
        praise.append({
            "quote": q1,
            "source": s1
        })

    q2 = clean_text(row.get("praise_2_quote"))
    s2 = clean_text(row.get("praise_2_source"))
    if q2 or s2:
        praise.append({
            "quote": q2,
            "source": s2
        })

    return praise


def build_videos(row):
    videos = []

    def clean(value):
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except Exception:
            pass
        return str(value).strip()

    for i in range(1, 4):  # supports video_1, video_2, and video_3
        title = clean(row.get(f"video_{i}_title", ""))
        description = clean(row.get(f"video_{i}_description", ""))
        youtube_id = clean(row.get(f"video_{i}_id", ""))

        if youtube_id:
            videos.append({
                "title": title,
                "description": description,
                "platform": "youtube",
                "id": youtube_id,
                "url": f"https://www.youtube.com/watch?v={youtube_id}",
                "embed": f"https://www.youtube.com/embed/{youtube_id}",
                "thumbnail": f"https://img.youtube.com/vi/{youtube_id}/hqdefault.jpg"
            })

    return videos


def build_editions(row: dict) -> list:
    editions = []

    blocks = [
        {
            "format": clean_text(row.get("format_1")),
            "publisher": clean_text(row.get("hc_publisher")),
            "price_usd": to_number(row.get("hc_price_usd")),
            "price_eur": to_number(row.get("hc_price_eur")),
            "price_gbp": to_number(row.get("hc_price_gbp")),
            "supplier": clean_text(row.get("hc_supplier")),
            "sku": clean_text(row.get("hc_sku")),
            "buy_link": clean_text(row.get("hc_buy_link")),
            "isbn": digits_only(row.get("hc_isbn")),
        },
        {
            "format": clean_text(row.get("format_2")),
            "publisher": clean_text(row.get("pb_publisher")),
            "price_usd": to_number(row.get("pb_price_usd")),
            "price_eur": to_number(row.get("pb_price_eur")),
            "price_gbp": to_number(row.get("pb_price_gbp")),
            "supplier": clean_text(row.get("pb_supplier")),
            "sku": clean_text(row.get("pb_sku")),
            "buy_link": clean_text(row.get("pb_buy_link")),
            "isbn": digits_only(row.get("pb_isbn")),
        },
        {
            "format": clean_text(row.get("format_3")),
            "publisher": clean_text(row.get("eb_publisher")),
            "price_usd": to_number(row.get("eb_price_usd")),
            "price_eur": to_number(row.get("eb_price_eur")),
            "price_gbp": to_number(row.get("eb_price_gbp")),
            "supplier": clean_text(row.get("eb_supplier")),
            "sku": clean_text(row.get("eb_sku")),
            "buy_link": clean_text(row.get("eb_buy_link")),
            "isbn": digits_only(row.get("eb_isbn")),
        },
    ]

    for ed in blocks:
        # Skip editions with no format at all
        if not ed["format"]:
            continue

        # Skip format rows that are otherwise entirely empty
        has_other_data = any(
            ed.get(key) is not None
            for key in ["publisher", "price_usd", "price_eur", "price_gbp", "supplier", "sku", "buy_link", "isbn"]
        )
        if not has_other_data:
            continue

        editions.append(sanitize_record(ed))

    return editions


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

    records = []

    for _, row in df.iterrows():
        row = row.to_dict()

        book = {
            "id": clean_text(row.get("id")),
            "title": clean_text(row.get("title")),
            "author": clean_text(row.get("author")),
            "translator": clean_text(row.get("translator")),
            "introduction": clean_text(row.get("introduction")),
            "cover": normalize_cover(row.get("cover")),
            "series": clean_text(row.get("series")),
            "series_number": to_number(row.get("series_number")),
            "category": clean_text(row.get("category")),
            "genre": clean_text(row.get("genre")),
            "shelf": clean_text(row.get("shelf")),
            "shelves": split_semicolon_list(row.get("shelves")),
            "tags": split_semicolon_list(row.get("tags")),
            "language_original": clean_text(row.get("language_original")),
            "description_short": clean_text(row.get("description_short")),
            "description_long": clean_text(row.get("description_long")),
            "publisher": clean_text(row.get("publisher")),  # book-level publisher, if you still use it
            "pages": to_number(row.get("pages")),
            "year": to_number(row.get("year")),
            "pub_date": clean_text(row.get("pub_date")),
            "featured": yes_no(row.get("featured")),
            "display_order": to_number(row.get("display_order")),
            "shelf_order": to_number(row.get("shelf_order")),
            "metadata_source": clean_text(row.get("metadata_source")),
            "videos": build_videos(row),
            "editions": build_editions(row),
        }

        praise = build_praise(row)
        if praise:
            book["praise"] = praise

        book = sanitize_record(book)

        # Skip rows with no essential identity
        if not book.get("id") and not book.get("title"):
            continue

        records.append(book)

    out_path = cwd / OUTPUT_JSON
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2, allow_nan=False)

    print(f"Wrote '{OUTPUT_JSON}' with {len(records)} books.")


if __name__ == "__main__":
    main()