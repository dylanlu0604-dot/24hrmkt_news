"""
reset_digests.py — 清除所有 AI 摘要，保留原始快訊
直接在 VS Code 按 ▶️ 執行
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "newsdesk.db"

if not DB_PATH.exists():
    print("❌ 找不到資料庫，請確認已執行過 main.py")
else:
    conn = sqlite3.connect(DB_PATH)
    digests_before = conn.execute("SELECT COUNT(*) FROM digests").fetchone()[0]
    flashes = conn.execute("SELECT COUNT(*) FROM flashes").fetchone()[0]

    conn.execute("DELETE FROM digests")
    conn.execute("UPDATE flashes SET digested = 0")
    conn.commit()
    conn.close()

    print(f"✅ 完成")
    print(f"   刪除摘要：{digests_before} 則")
    print(f"   保留快訊：{flashes} 則（已重置為未摘要）")
    print(f"\n重新啟動 main.py 後，AI 會重新產生摘要。")
