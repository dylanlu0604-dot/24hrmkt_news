"""
summarizer.py — Every 15 min, take unseen flashes → ask OpenAI to produce
5-10 digest items → store to digests table.
"""

import os
import json
from datetime import datetime, timedelta, timezone
from openai import OpenAI

import db
from config import CATEGORIES

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def now_taipei() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def summarize(flashes: list) -> list:
    """
    Given a list of flash dicts, call OpenAI to produce 5-10 digest items.
    Returns a list of dicts: {title_zh, content_zh, content_en, categories}
    """
    numbered = "\n".join(
        f"{i+1}. [{f['time_taipei']}] {f['content_en']}"
        for i, f in enumerate(flashes)
    )

    categories_json = json.dumps(CATEGORIES, ensure_ascii=False)
    example = '{"digests": [{"title_zh": "...", "content_zh": "...", "content_en": "...", "categories": [...]}, ...]}'

    prompt = (
        f"You are a senior financial news editor covering global markets.\n\n"
        f"Below are {len(flashes)} raw market flash news items from the past 100 minutes.\n\n"
        "Your task:\n"
        "1. Group related flashes and write 20-35 concise digest summaries in Traditional Chinese.\n"
        "2. Each digest should synthesize related items into ONE clear narrative.\n"
        "3. For each digest, provide:\n"
        '   - "title_zh": A direct, conclusion-first Traditional Chinese headline (<=25 characters).\n'
        '     Write the KEY CONCLUSION, not just the topic.\n'
        '     Example: "Fed暗示暫停升息" not just "Fed利率動向"\n'
        '   - "content_zh": MUST be written entirely in Traditional Chinese (繁體中文). No English whatsoever.\n'
        '     * If the source contains analysis, context, or implications → preserve and rewrite them in your own words in Traditional Chinese\n'
        '     * If the source is purely price/data movement → report numbers only, NO added analysis or filler\n'
        '     * ALWAYS forbidden: "反映出"、"顯示出"、"值得注意"、"這表明"、"分析人士認為"、"市場情緒"\n'
        '     * 100% forbidden: "反映出"、"顯示出"、"值得注意"、"這表明"、"分析人士認為"、"市場情緒"\n'
        '     * Write in neutral wire-service style. Include all important names, numbers, and details.\n'
        '   - "categories": Array of categories. You MUST only use EXACT strings from this list, no modifications, no additions:\n'
        f"     {categories_json}\n"
        "     If none match, use an empty array. Do NOT invent new categories or append extra words.\n\n"
        'Return ONLY a JSON object with a single key "digests" containing an array of digest objects.\n'
        f"Example format: "
        '{"digests": [{"flash_indices": [1, 3], "title_zh": "...", "content_zh": "...", "content_en": "...", "categories": [...]}, ...]}\n'
        "No preamble, no markdown, no other keys.\n\n"
        f"Flash items:\n{numbered}"
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    # Handle various JSON shapes from the model
    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        # Try common wrapper keys
        for key in ("digests", "items", "summaries", "results", "news"):
            if key in parsed and isinstance(parsed[key], list):
                items = parsed[key]
                break
        else:
            # If the dict itself looks like a single digest item, wrap it
            if "title_zh" in parsed:
                items = [parsed]
            else:
                # Collect all dict values that look like digest items
                items = [v for v in parsed.values() if isinstance(v, dict)]
            if not items:
                print(f"[summarizer] Unexpected JSON shape, keys: {list(parsed.keys())}")
                return []
    else:
        return []

    return items


def run_summarizer():
    """Main entry: fetch undigested flashes → summarize → mark as digested → store."""
    flashes = db.get_undigested_flashes()

    if not flashes:
        print("[summarizer] No undigested flashes — skipping")
        return 0

    # 最多 60 筆，避免 prompt 過長
    flashes = flashes[:60]

    print(f"[summarizer] Summarizing {len(flashes)} undigested flashes …")

    try:
        items = summarize(flashes)
    except Exception as e:
        print(f"[summarizer] OpenAI error: {e}")
        return 0

    now   = now_taipei()
    times = [f["time_taipei"] for f in flashes]
    p_start = min(times)
    p_end   = max(times)
    ids     = [f["id"] for f in flashes]

    saved = 0
    for item in items:
        try:
            # 過濾掉不在 CATEGORIES 清單內的標籤
            raw_cats = item.get("categories", [])
            valid_cats = [c for c in raw_cats if c in CATEGORIES]

            # 用 flash_indices 算出這則摘要對應快訊的最晚時間
            indices = item.get("flash_indices", [])
            if indices:
                used = [flashes[i-1] for i in indices if 1 <= i <= len(flashes)]
            else:
                used = flashes
            item_times = [f["time_taipei"] for f in used]
            item_end   = max(item_times) if item_times else p_end
            item_start = min(item_times) if item_times else p_start
            item_ids   = [f["id"] for f in used]

            db.insert_digest({
                "created_at":   now,
                "period_start": item_start,
                "period_end":   item_end,
                "flash_ids":    item_ids,
                "title_zh":     item.get("title_zh", ""),
                "content_zh":   item.get("content_zh", ""),
                "content_en":   item.get("content_en", ""),
                "categories":   valid_cats,
            })
            saved += 1
        except Exception as e:
            print(f"[summarizer] insert error: {e}")

    print(f"[summarizer] Saved {saved} digest(s).")

    # 標記這批快訊為已摘要，下次不重複處理
    if saved > 0:
        db.mark_flashes_digested(ids)

    return saved


if __name__ == "__main__":
    db.init_db()
    run_summarizer()