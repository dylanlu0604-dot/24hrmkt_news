"""
push.py — 一鍵匯出資料並推送到 GitHub
在 VS Code 直接按 ▶️ 執行
"""

import subprocess
import sys
from pathlib import Path
import exporter

ROOT = Path(__file__).parent


def run(cmd: str):
    print(f"$ {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    return result.returncode == 0


def main():
    print("📦 匯出資料...")
    exporter.export()

    print("\n🚀 推送到 GitHub...")
    run("git add docs/data.json")
    run('git commit -m "update: refresh digest data"')

    if not run("git push"):
        print("\n❌ Push 失敗，請確認：")
        print("   1. 已設定 git remote: git remote add origin https://github.com/dylanlu0604-dot/24hrmkt_news.git")
        print("   2. 已登入 GitHub")
        sys.exit(1)

    print("\n✅ 完成！網站資料已更新")
    print("🌐 https://dylanlu0604-dot.github.io/24hrmkt_news")


if __name__ == "__main__":
    main()
