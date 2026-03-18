"""
fetcher.py — Pull raw flash news from api.mktnews.net and store to SQLite.
"""

import re
import requests
from datetime import datetime, timedelta, timezone

import db

API_URL = "https://api.mktnews.net/api/flash"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; NewsDesk/2.0)",
}


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def utc_to_taipei(utc_str: str) -> str:
    dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    taipei_tz = timezone(timedelta(hours=8))
    return dt.astimezone(taipei_tz).strftime("%Y-%m-%d %H:%M:%S")


def fetch_page(page: int = 1, size: int = 30) -> list:
    try:
        resp = requests.get(
            API_URL,
            params={"page": page, "size": size},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", []) if data.get("status") == 200 else []
    except Exception as e:
        print(f"[fetcher] API error: {e}")
        return []


def fetch_and_store(pages: int = 1) -> int:
    """Fetch `pages` pages and store new flashes. Returns count of new rows."""
    new_count = 0
    for page in range(1, pages + 1):
        items = fetch_page(page=page, size=30)
        if not items:
            break
        for item in items:
            content = clean_html(item["data"].get("content", ""))
            title   = clean_html(item["data"].get("title", ""))
            full    = f"{title}\n{content}".strip() if title else content

            if not full:
                continue

            row = {
                "id":          item["id"],
                "time_utc":    item["time"],
                "time_taipei": utc_to_taipei(item["time"]),
                "important":   item.get("important", 0),
                "hot":         item.get("hot", False),
                "content_en":  full,
                "impact":      [
                    {"symbol": x["symbol"], "impact": x["impact"]}
                    for x in (item.get("impact") or [])
                    if x.get("symbol")
                ],
                "tags": [
                    c["name"] for c in (item.get("classification") or [])
                ],
            }
            if db.insert_flash(row):
                new_count += 1
    return new_count


if __name__ == "__main__":
    db.init_db()
    n = fetch_and_store(pages=1)
    print(f"Stored {n} new flashes.")
