"""
exporter.py — 將 SQLite 的摘要匯出成 docs/data.json，供 GitHub Pages 讀取
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH   = Path(__file__).parent / "data" / "newsdesk.db"
OUT_PATH  = Path(__file__).parent / "docs" / "data.json"


def export():
    if not DB_PATH.exists():
        print("❌ 找不到資料庫")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    digests = conn.execute("""
        SELECT id, created_at, period_start, period_end,
               title_zh, content_zh, categories
        FROM digests
        ORDER BY period_end DESC
        LIMIT 500
    """).fetchall()

    flashes_count = conn.execute("SELECT COUNT(*) FROM flashes").fetchone()[0]
    conn.close()

    result = []
    for d in digests:
        result.append({
            "id":          d["id"],
            "time":        d["period_end"],        # 最新快訊時間
            "title_zh":    d["title_zh"],
            "content_zh":  d["content_zh"],
            "categories":  json.loads(d["categories"] or "[]"),
        })

    tz = timezone(timedelta(hours=8))
    updated_at = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    output = {
        "updated_at":    updated_at,
        "digest_count":  len(result),
        "flash_count":   flashes_count,
        "digests":       result,
    }

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 匯出 {len(result)} 則摘要 → {OUT_PATH}")


if __name__ == "__main__":
    export()
