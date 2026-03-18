"""
main.py — Entry point with Rich live status dashboard.
"""

import os
import time
import threading
import logging
from datetime import datetime, timedelta, timezone

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import db
import fetcher
import summarizer
import exporter
from app import app
from config import FETCH_INTERVAL, SUMMARIZE_INTERVAL

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

# ── Shared state ──────────────────────────────────────────────────────
state = {
    "flash_total":      0,
    "flash_new":        0,
    "flash_last_run":   "—",
    "flash_next_run":   "—",
    "flash_status":     "waiting",

    "digest_total":     0,
    "digest_new":       0,
    "digest_last_run":  "—",
    "digest_next_run":  "—",
    "digest_status":    "waiting",

    "web_port":         5050,
    "log_lines":        [],
}

MAX_LOGS = 8


def ts() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%H:%M:%S")


def add_log(msg: str):
    state["log_lines"].append(f"[dim]{ts()}[/dim]  {msg}")
    if len(state["log_lines"]) > MAX_LOGS:
        state["log_lines"].pop(0)


def next_run_str(seconds_from_now: int) -> str:
    tz = timezone(timedelta(hours=8))
    t = datetime.now(tz) + timedelta(seconds=seconds_from_now)
    return t.strftime("%H:%M:%S")


def build_dashboard() -> Panel:
    def status_badge(s):
        colours = {
            "waiting":     ("dim white",   "◌  等待中"),
            "fetching":    ("yellow",      "⟳  爬取中"),
            "summarizing": ("cyan",        "🤖 AI 生成中"),
            "ok":          ("green",       "✓  完成"),
            "error":       ("red",         "✗  錯誤"),
            "skipped":     ("dim yellow",  "–  無新快訊"),
        }
        colour, label = colours.get(s, ("white", s))
        return f"[{colour}]{label}[/{colour}]"

    t1 = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t1.add_column(style="dim", width=14)
    t1.add_column()
    t1.add_row("狀態",     status_badge(state["flash_status"]))
    t1.add_row("上次執行", state["flash_last_run"])
    t1.add_row("下次執行", state["flash_next_run"])
    t1.add_row("本次新增", f"[yellow]+{state['flash_new']}[/yellow] 則")
    t1.add_row("資料庫累計", f"[bold]{state['flash_total']}[/bold] 則快訊")

    t2 = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t2.add_column(style="dim", width=14)
    t2.add_column()
    t2.add_row("狀態",     status_badge(state["digest_status"]))
    t2.add_row("上次執行", state["digest_last_run"])
    t2.add_row("下次執行", state["digest_next_run"])
    t2.add_row("本次新增", f"[cyan]+{state['digest_new']}[/cyan] 則摘要")
    t2.add_row("資料庫累計", f"[bold]{state['digest_total']}[/bold] 則摘要")

    body = Table.grid(padding=(0, 2))
    body.add_column(ratio=1)
    body.add_column(ratio=1)
    body.add_row(
        Panel(t1, title="[bold yellow]📡  爬蟲[/bold yellow]",
              border_style="yellow", padding=(0, 1)),
        Panel(t2, title="[bold cyan]🤖  AI 摘要[/bold cyan]",
              border_style="cyan", padding=(0, 1)),
    )

    from rich.rule import Rule
    log_text = Text.from_markup(
        "\n".join(state["log_lines"]) or "[dim]（尚無紀錄）[/dim]"
    )

    grid = Table.grid()
    grid.add_column()
    grid.add_row(body)
    grid.add_row(Rule(style="dim"))
    grid.add_row(Panel(log_text, title="[dim]最新紀錄[/dim]",
                       border_style="dim", padding=(0, 1)))

    return Panel(
        grid,
        title=f"[bold white]NewsDesk[/bold white]  "
              f"[dim]http://localhost:{state['web_port']}[/dim]",
        border_style="white",
    )


def fetch_loop():
    add_log("📡 爬蟲啟動")
    while True:
        state["flash_status"] = "fetching"
        add_log("⟳  開始爬取 API…")
        try:
            n = fetcher.fetch_and_store(pages=1)
            with db.get_conn() as conn:
                state["flash_total"] = conn.execute(
                    "SELECT COUNT(*) FROM flashes").fetchone()[0]
            state["flash_new"]      = n
            state["flash_last_run"] = ts()
            state["flash_next_run"] = next_run_str(FETCH_INTERVAL)
            state["flash_status"]   = "ok"
            add_log(f"[green]✓  爬取完成[/green] 新增 [yellow]+{n}[/yellow] 則，"
                    f"累計 {state['flash_total']} 則")
        except Exception as e:
            state["flash_status"] = "error"
            add_log(f"[red]✗  爬取失敗：{e}[/red]")
        time.sleep(FETCH_INTERVAL)


def summarize_loop():
    time.sleep(10)   # 等 fetcher 先跑完
    add_log("🤖 AI 摘要啟動")
    while True:
        state["digest_status"] = "summarizing"
        add_log("⟳  AI 開始整理摘要…")
        try:
            n = summarizer.run_summarizer()
            with db.get_conn() as conn:
                state["digest_total"] = conn.execute(
                    "SELECT COUNT(*) FROM digests").fetchone()[0]
            state["digest_new"]      = n
            state["digest_last_run"] = ts()
            state["digest_next_run"] = next_run_str(SUMMARIZE_INTERVAL)
            if n:
                state["digest_status"] = "ok"
                add_log(f"[cyan]✓  摘要完成[/cyan] 新增 [cyan]+{n}[/cyan] 則，"
                        f"累計 {state['digest_total']} 則")
                # 自動匯出 docs/data.json
                try:
                    exporter.export()
                    add_log("[dim]↑  data.json 已更新，執行 push.py 可同步到網站[/dim]")
                except Exception as ex:
                    add_log(f"[dim red]↑  匯出失敗：{ex}[/dim red]")
            else:
                state["digest_status"] = "skipped"
                add_log("[dim yellow]–  近 15 分鐘無新快訊，跳過本次[/dim yellow]")
        except Exception as e:
            state["digest_status"] = "error"
            add_log(f"[red]✗  AI 摘要失敗：{e}[/red]")
        time.sleep(SUMMARIZE_INTERVAL)


def flask_thread():
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    port = int(os.environ.get("PORT", 5050))
    state["web_port"] = port
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("❌  OPENAI_API_KEY not set. Add it to .env")

    os.makedirs("data", exist_ok=True)
    db.init_db()

    with db.get_conn() as conn:
        state["flash_total"]  = conn.execute(
            "SELECT COUNT(*) FROM flashes").fetchone()[0]
        state["digest_total"] = conn.execute(
            "SELECT COUNT(*) FROM digests").fetchone()[0]

    state["flash_next_run"]  = next_run_str(0)
    state["digest_next_run"] = next_run_str(30)

    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    threading.Thread(target=fetch_loop,     daemon=True).start()
    threading.Thread(target=summarize_loop, daemon=True).start()
    threading.Thread(target=flask_thread,   daemon=True).start()

    with Live(build_dashboard(), refresh_per_second=1, console=console) as live:
        while True:
            live.update(build_dashboard())
            time.sleep(1)


if __name__ == "__main__":
    main()