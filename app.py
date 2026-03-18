"""
app.py — Flask web server for NewsDesk UI (摘要 + 原始快訊 兩個分頁)
"""

import os
import json
from flask import Flask, render_template_string, jsonify, request
import db
from config import CATEGORIES

app = Flask(__name__)

HTML = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NewsDesk — 市場情報摘要</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:       #0a0a0f;
    --surface:  #111118;
    --border:   #1e1e2e;
    --accent:   #e8c97d;
    --accent2:  #7dd3e8;
    --text:     #e8e6df;
    --muted:    #6b6b7a;
    --tag-bg:   #1a1a28;
    --green:    #7de8a0;
    --red:      #e87d7d;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:'Noto Serif TC',serif; min-height:100vh; }

  /* HEADER */
  header {
    border-bottom:1px solid var(--border);
    padding:0 2rem;
    display:flex; align-items:center; justify-content:space-between;
    height:64px; position:sticky; top:0;
    background:rgba(10,10,15,0.95); backdrop-filter:blur(12px); z-index:100;
  }
  .logo { font-family:'Space Mono',monospace; font-size:1.1rem; font-weight:700; letter-spacing:.08em; color:var(--accent); }
  .logo span { color:var(--accent2); }
  .last-updated { font-family:'Space Mono',monospace; font-size:.7rem; color:var(--muted); text-align:right; line-height:1.6; }
  .live-dot { display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--green); margin-right:6px; animation:pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

  /* TABS */
  .tabs {
    display:flex; gap:0; border-bottom:1px solid var(--border);
    padding:0 2rem; background:var(--bg);
    position:sticky; top:64px; z-index:99;
  }
  .tab-btn {
    font-family:'Space Mono',monospace; font-size:.78rem; letter-spacing:.06em;
    padding:.75rem 1.5rem; border:none; background:transparent;
    color:var(--muted); cursor:pointer; border-bottom:2px solid transparent;
    transition:all .15s ease;
  }
  .tab-btn:hover { color:var(--text); }
  .tab-btn.active { color:var(--accent); border-bottom-color:var(--accent); }

  /* LAYOUT */
  .container { max-width:900px; margin:0 auto; padding:2rem 1.5rem 4rem; }
  .tab-panel { display:none; }
  .tab-panel.active { display:block; }

  /* STATS */
  .stats-bar { display:flex; gap:2rem; margin-bottom:1.5rem; }
  .stat { font-family:'Space Mono',monospace; font-size:.7rem; color:var(--muted); }
  .stat strong { display:block; font-size:1.4rem; color:var(--accent); font-weight:700; }

  /* FILTER */
  .filter-bar { display:flex; flex-wrap:wrap; gap:.5rem; margin-bottom:2rem; padding:1rem 0; border-bottom:1px solid var(--border); }
  .tag-btn { font-family:'Noto Serif TC',serif; font-size:.78rem; padding:.3rem .8rem; border-radius:2px; border:1px solid var(--border); background:var(--tag-bg); color:var(--muted); cursor:pointer; transition:all .15s ease; }
  .tag-btn:hover { border-color:var(--accent); color:var(--accent); }
  .tag-btn.active { background:var(--accent); color:#0a0a0f; border-color:var(--accent); font-weight:600; }

  /* DIGEST CARDS */
  .digests-grid { display:flex; flex-direction:column; }
  .digest-card { border-bottom:1px solid var(--border); padding:1.5rem 0; display:grid; grid-template-columns:80px 1fr; gap:1.5rem; animation:fadeIn .4s ease both; }
  .digest-card.hidden { display:none; }
  @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
  .digest-time { font-family:'Space Mono',monospace; font-size:.68rem; color:var(--muted); line-height:1.5; padding-top:4px; }
  .digest-time .date { display:block; }
  .digest-time .time { display:block; color:var(--accent); }
  .digest-title { font-size:1.05rem; font-weight:700; line-height:1.4; margin-bottom:.6rem; }
  .digest-content { font-size:.88rem; color:#b0aead; line-height:1.8; margin-bottom:.8rem; }
  .digest-tags { display:flex; flex-wrap:wrap; gap:.4rem; }
  .digest-tag { font-family:'Space Mono',monospace; font-size:.65rem; padding:.15rem .55rem; border-radius:2px; background:var(--tag-bg); color:var(--accent2); border:1px solid rgba(125,211,232,.2); }

  /* FLASH CARDS */
  .flashes-list { display:flex; flex-direction:column; }
  .flash-card { border-bottom:1px solid var(--border); padding:1rem 0; display:grid; grid-template-columns:80px 1fr; gap:1.2rem; animation:fadeIn .3s ease both; }
  .flash-time { font-family:'Space Mono',monospace; font-size:.68rem; color:var(--muted); line-height:1.5; padding-top:2px; }
  .flash-time .date { display:block; }
  .flash-time .time { display:block; color:var(--accent); }
  .flash-content { font-size:.85rem; color:var(--text); line-height:1.7; }
  .flash-meta { display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.5rem; align-items:center; }
  .flash-tag { font-family:'Space Mono',monospace; font-size:.62rem; padding:.1rem .45rem; border-radius:2px; background:var(--tag-bg); color:var(--accent2); border:1px solid rgba(125,211,232,.15); }
  .flash-impact { font-family:'Space Mono',monospace; font-size:.62rem; padding:.1rem .45rem; border-radius:2px; }
  .flash-impact.bullish { background:rgba(125,232,160,.1); color:var(--green); border:1px solid rgba(125,232,160,.2); }
  .flash-impact.bearish { background:rgba(232,125,125,.1); color:var(--red); border:1px solid rgba(232,125,125,.2); }
  .flash-impact.mixed, .flash-impact.none { background:var(--tag-bg); color:var(--muted); border:1px solid var(--border); }
  .hot-badge { font-family:'Space Mono',monospace; font-size:.62rem; padding:.1rem .45rem; border-radius:2px; background:rgba(232,201,125,.15); color:var(--accent); border:1px solid rgba(232,201,125,.3); }

  /* SEARCH */
  .search-bar { margin-bottom:1.5rem; }
  .search-bar input { width:100%; background:var(--surface); border:1px solid var(--border); color:var(--text); font-family:'Space Mono',monospace; font-size:.82rem; padding:.6rem 1rem; border-radius:2px; outline:none; transition:border-color .15s; }
  .search-bar input:focus { border-color:var(--accent); }
  .search-bar input::placeholder { color:var(--muted); }

  /* EMPTY */
  .empty { text-align:center; padding:4rem 0; color:var(--muted); font-family:'Space Mono',monospace; font-size:.85rem; line-height:2; }

  ::-webkit-scrollbar { width:4px; }
  ::-webkit-scrollbar-track { background:var(--bg); }
  ::-webkit-scrollbar-thumb { background:var(--border); border-radius:2px; }

  @media(max-width:600px) {
    .digest-card, .flash-card { grid-template-columns:1fr; gap:.5rem; }
    header { padding:0 1rem; }
    .tabs { padding:0 1rem; }
  }
</style>
</head>
<body>

<header>
  <div class="logo">NEWS<span>DESK</span></div>
  <div class="last-updated" id="lastUpdated"><span class="live-dot"></span>載入中…</div>
</header>

<!-- TABS -->
<div class="tabs">
  <button class="tab-btn active" data-tab="digests">📋 AI 摘要</button>
  <button class="tab-btn" data-tab="flashes">⚡ 原始快訊</button>
</div>

<div class="container">

  <!-- ── 摘要分頁 ── -->
  <div class="tab-panel active" id="tab-digests">
    <div class="stats-bar">
      <div class="stat"><strong id="totalCount">—</strong>今日摘要</div>
      <div class="stat"><strong id="flashCount">—</strong>原始快訊</div>
    </div>
    <div class="filter-bar">
      <button class="tag-btn active" data-cat="">全部</button>
      {% for cat in categories %}
      <button class="tag-btn" data-cat="{{ cat }}">{{ cat }}</button>
      {% endfor %}
    </div>
    <div class="digests-grid" id="digestsGrid"><div class="empty">載入中…</div></div>
  </div>

  <!-- ── 原始快訊分頁 ── -->
  <div class="tab-panel" id="tab-flashes">
    <div class="stats-bar">
      <div class="stat"><strong id="flashTotalCount">—</strong>快訊總數</div>
    </div>
    <div class="search-bar">
      <input type="text" id="flashSearch" placeholder="搜尋關鍵字…" oninput="filterFlashes()">
    </div>
    <div class="flashes-list" id="flashesList"><div class="empty">載入中…</div></div>
  </div>

</div>

<script>
let allDigests = [];
let allFlashes = [];
let activeCategory = '';

// ── Tab switching ──────────────────────────────────────────────────
document.querySelector('.tabs').addEventListener('click', e => {
  const btn = e.target.closest('.tab-btn');
  if (!btn) return;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
});

// ── Digests ────────────────────────────────────────────────────────
function renderDigests(digests) {
  const grid = document.getElementById('digestsGrid');
  if (!digests.length) {
    grid.innerHTML = '<div class="empty">目前暫無摘要<br>等待下次 AI 整理中…</div>';
    return;
  }
  grid.innerHTML = digests.map((d, i) => {
    const parts = (d.period_end || d.created_at || '').split(' ');
    const timeStr = (parts[1] || '').slice(0, 5); // HH:MM only
    const tags = (d.categories || []).map(c => `<span class="digest-tag">${c}</span>`).join('');
    return `
      <div class="digest-card" style="animation-delay:${i*.04}s" data-cats='${JSON.stringify(d.categories||[])}'>
        <div class="digest-time">
          <span class="date">${parts[0]||'—'}</span>
          <span class="time">${timeStr}</span>
        </div>
        <div>
          <div class="digest-title">${d.title_zh}</div>
          <div class="digest-content">${d.content_zh}</div>
          ${tags ? `<div class="digest-tags">${tags}</div>` : ''}
        </div>
      </div>`;
  }).join('');
}

function filterDigests(cat) {
  document.querySelectorAll('.digest-card').forEach(card => {
    if (!cat) { card.classList.remove('hidden'); return; }
    const cats = JSON.parse(card.dataset.cats || '[]');
    card.classList.toggle('hidden', !cats.includes(cat));
  });
}

// ── Flashes ────────────────────────────────────────────────────────
function renderFlashes(flashes) {
  const list = document.getElementById('flashesList');
  if (!flashes.length) {
    list.innerHTML = '<div class="empty">暫無原始快訊</div>';
    return;
  }
  list.innerHTML = flashes.map((f, i) => {
    const parts = (f.time_taipei || '').split(' ');
    const tags = (f.tags || []).map(t => `<span class="flash-tag">${t}</span>`).join('');
    const impacts = (f.impact || []).map(imp =>
      `<span class="flash-impact ${imp.impact}">${imp.symbol}</span>`
    ).join('');
    const hot = f.hot ? '<span class="hot-badge">🔥 HOT</span>' : '';
    const meta = [hot, tags, impacts].filter(Boolean).join('');
    return `
      <div class="flash-card" style="animation-delay:${i*.02}s">
        <div class="flash-time">
          <span class="date">${parts[0]||'—'}</span>
          <span class="time">${parts[1]||''}</span>
        </div>
        <div>
          <div class="flash-content">${f.content_en}</div>
          ${meta ? `<div class="flash-meta">${meta}</div>` : ''}
        </div>
      </div>`;
  }).join('');
  document.getElementById('flashTotalCount').textContent = flashes.length;
}

function filterFlashes() {
  const q = document.getElementById('flashSearch').value.toLowerCase();
  if (!q) { renderFlashes(allFlashes); return; }
  renderFlashes(allFlashes.filter(f => f.content_en.toLowerCase().includes(q)));
}

// ── Data fetching ──────────────────────────────────────────────────
async function loadAll() {
  const [dRes, fRes, sRes] = await Promise.all([
    fetch('/api/digests'),
    fetch('/api/flashes'),
    fetch('/api/stats'),
  ]);
  const dData = await dRes.json();
  const fData = await fRes.json();
  const sData = await sRes.json();

  allDigests = (dData.digests || []).sort((a, b) =>
    (b.period_end || '').localeCompare(a.period_end || ''));
  allFlashes = (fData.flashes || []).sort((a, b) =>
    (b.time_taipei || '').localeCompare(a.time_taipei || ''));

  renderDigests(allDigests);
  filterDigests(activeCategory);
  renderFlashes(allFlashes);

  document.getElementById('totalCount').textContent = allDigests.length;
  document.getElementById('flashCount').textContent = allFlashes.length;

  const lu = document.getElementById('lastUpdated');
  lu.innerHTML = `<span class="live-dot"></span>最後更新<br>${sData.last_updated || '—'}`;
}

// Category filter
document.querySelector('.filter-bar').addEventListener('click', e => {
  const btn = e.target.closest('.tag-btn');
  if (!btn) return;
  document.querySelectorAll('.filter-bar .tag-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeCategory = btn.dataset.cat;
  filterDigests(activeCategory);
});

loadAll();
setInterval(loadAll, 60000);
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML, categories=CATEGORIES)

@app.route("/api/digests")
def api_digests():
    category = request.args.get("category", "")
    digests  = db.get_digests(limit=200, category=category or None)
    return jsonify({"digests": digests})

@app.route("/api/flashes")
def api_flashes():
    flashes = db.get_flashes(limit=200)
    return jsonify({"flashes": flashes})

@app.route("/api/stats")
def api_stats():
    with db.get_conn() as conn:
        flash_count = conn.execute("SELECT COUNT(*) FROM flashes").fetchone()[0]
    return jsonify({
        "flash_count":  flash_count,
        "last_updated": db.get_last_updated(),
    })

if __name__ == "__main__":
    db.init_db()
    port = int(os.environ.get("PORT", 5050))
    print(f"🌐  NewsDesk running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)