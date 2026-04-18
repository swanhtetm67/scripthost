import os
import sqlite3
import random
import string
from datetime import datetime
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse

# ─────────────────────────────────────────────
#  CONFIG & DATABASE
# ─────────────────────────────────────────────
DB_PATH  = os.environ.get("DB_PATH", "/tmp/scripthost.db")
APP_NAME = "ScriptHost"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scripts (
                id         TEXT PRIMARY KEY,
                title      TEXT NOT NULL,
                views      INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS versions (
                script_id TEXT NOT NULL,
                content   TEXT NOT NULL,
                v         INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (script_id, v)
            );
        """)

init_db()
app = FastAPI(title=APP_NAME)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def gen_id(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

def alert(msg: str, kind: str = "error") -> str:
    styles = {
        "error":   ("bg-red-500/10 border-red-500/30 text-red-300",    "⚠️"),
        "success": ("bg-emerald-500/10 border-emerald-500/30 text-emerald-300", "✅"),
        "info":    ("bg-indigo-500/10 border-indigo-500/30 text-indigo-300", "ℹ️"),
    }
    cls, icon = styles.get(kind, styles["error"])
    return f"""
    <div class="flex items-center gap-3 mb-5 px-4 py-3 rounded-xl border {cls} text-sm animate-fade-in">
        <span>{icon}</span> {msg}
    </div>"""


# ─────────────────────────────────────────────
#  BASE LAYOUT
# ─────────────────────────────────────────────
def layout(content: str, title: str = APP_NAME) -> str:
    return f"""<!DOCTYPE html>
<html lang="en" class="scroll-smooth">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — {APP_NAME}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: 'Inter', sans-serif;
      background: #020817;
      color: #e2e8f0;
      min-height: 100dvh;
    }}
    .mono {{ font-family: 'JetBrains Mono', monospace; }}

    /* Animated gradient background */
    body::before {{
      content: '';
      position: fixed;
      inset: 0;
      background:
        radial-gradient(ellipse 90% 70% at 5% -10%, rgba(99,102,241,.22) 0%, transparent 55%),
        radial-gradient(ellipse 70% 60% at 95% 110%, rgba(139,92,246,.16) 0%, transparent 55%),
        radial-gradient(ellipse 50% 40% at 50% 50%, rgba(16,185,129,.05) 0%, transparent 60%);
      pointer-events: none;
      z-index: 0;
    }}

    /* Grid pattern */
    body::after {{
      content: '';
      position: fixed;
      inset: 0;
      background-image: linear-gradient(rgba(99,102,241,.04) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(99,102,241,.04) 1px, transparent 1px);
      background-size: 40px 40px;
      pointer-events: none;
      z-index: 0;
    }}

    .glass {{
      background: rgba(255,255,255,.03);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(255,255,255,.07);
    }}
    .glass-card {{
      background: rgba(15,23,42,.6);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255,255,255,.07);
      transition: border-color .25s, background .25s, transform .2s, box-shadow .25s;
    }}
    .glass-card:hover {{
      background: rgba(15,23,42,.8);
      border-color: rgba(99,102,241,.3);
      box-shadow: 0 8px 32px rgba(99,102,241,.08);
    }}

    input, textarea, select {{
      background: rgba(15,23,42,.8) !important;
      border: 1px solid rgba(255,255,255,.1) !important;
      color: #e2e8f0 !important;
      outline: none !important;
      transition: border-color .2s, box-shadow .2s !important;
    }}
    input::placeholder, textarea::placeholder {{
      color: #334155 !important;
    }}
    input:focus, textarea:focus {{
      border-color: #6366f1 !important;
      box-shadow: 0 0 0 3px rgba(99,102,241,.15) !important;
    }}

    .btn-primary {{
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
      color: white;
      font-weight: 600;
      transition: opacity .2s, transform .15s, box-shadow .2s;
      box-shadow: 0 4px 15px rgba(99,102,241,.3);
    }}
    .btn-primary:hover {{ opacity: .92; transform: translateY(-1px); box-shadow: 0 6px 20px rgba(99,102,241,.4); }}
    .btn-primary:active {{ transform: translateY(0); }}

    .btn-ghost {{
      background: rgba(255,255,255,.05);
      border: 1px solid rgba(255,255,255,.08);
      color: #94a3b8;
      font-weight: 500;
      transition: all .2s;
    }}
    .btn-ghost:hover {{ background: rgba(255,255,255,.09); color: #e2e8f0; border-color: rgba(255,255,255,.15); }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: .3rem;
      padding: .2rem .65rem;
      border-radius: 9999px;
      font-size: .7rem;
      font-weight: 600;
      letter-spacing: .02em;
    }}

    .loadstring-box {{
      background: #0a1628;
      border: 1px solid rgba(99,102,241,.25);
      border-radius: .75rem;
      padding: .75rem 1rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: .72rem;
      color: #a5b4fc;
      word-break: break-all;
      line-height: 1.7;
      position: relative;
      cursor: pointer;
      transition: border-color .2s, background .2s;
      user-select: none;
    }}
    .loadstring-box:hover {{
      border-color: rgba(99,102,241,.5);
      background: #0d1e38;
    }}

    /* Toast */
    #toast {{
      position: fixed; bottom: 1.5rem; right: 1.5rem;
      transform: translateY(5rem); opacity: 0;
      transition: all .4s cubic-bezier(.34,1.56,.64,1);
      z-index: 9999;
    }}
    #toast.show {{ transform: translateY(0); opacity: 1; }}
    #toast.error {{ background: #dc2626 !important; }}

    /* Tab system */
    .tab-btn {{ transition: all .2s; }}
    .tab-btn.active {{
      background: rgba(99,102,241,.2);
      color: #a5b4fc;
      border-color: rgba(99,102,241,.3);
    }}

    /* File drop zone */
    .drop-zone {{
      border: 2px dashed rgba(99,102,241,.25);
      border-radius: .75rem;
      transition: all .2s;
      cursor: pointer;
    }}
    .drop-zone:hover, .drop-zone.dragover {{
      border-color: rgba(99,102,241,.6);
      background: rgba(99,102,241,.05);
    }}

    /* Scrollbar */
    ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: #1e293b; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #334155; }}

    /* Logo */
    .logo-text {{
      background: linear-gradient(135deg, #a5b4fc, #7c3aed);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    /* Stat glow */
    .stat-indigo {{ text-shadow: 0 0 20px rgba(99,102,241,.5); }}
    .stat-violet {{ text-shadow: 0 0 20px rgba(139,92,246,.5); }}
    .stat-emerald {{ text-shadow: 0 0 20px rgba(16,185,129,.5); }}

    @keyframes fade-in {{
      from {{ opacity:0; transform:translateY(-6px); }}
      to   {{ opacity:1; transform:translateY(0); }}
    }}
    .animate-fade-in {{ animation: fade-in .3s ease; }}

    @keyframes slide-up {{
      from {{ opacity:0; transform:translateY(20px); }}
      to   {{ opacity:1; transform:translateY(0); }}
    }}
    .animate-slide-up {{ animation: slide-up .5s ease both; }}

    /* Mobile nav */
    #mobile-menu {{ display: none; }}
    #mobile-menu.open {{ display: block; }}
  </style>
</head>
<body class="relative">
<div class="relative z-10">

  <!-- ── NAV ── -->
  <header class="sticky top-0 z-50 border-b border-white/5 glass">
    <nav class="max-w-6xl mx-auto flex items-center justify-between px-4 sm:px-6 h-14">
      <a href="/" class="flex items-center gap-2.5 shrink-0 group">
        <div class="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600
                    flex items-center justify-center text-sm font-black shadow-lg
                    shadow-indigo-500/30 group-hover:shadow-indigo-500/50 transition-shadow">S</div>
        <span class="font-black text-base tracking-tight logo-text">{APP_NAME}</span>
      </a>
      <!-- Desktop nav -->
      <div class="hidden sm:flex items-center gap-2">
        <a href="/" class="text-sm font-medium text-slate-400 hover:text-white px-3 py-1.5 rounded-lg
                            hover:bg-white/5 transition-all">Home</a>
        <a href="/dashboard" class="text-sm font-semibold btn-primary px-4 py-2 rounded-xl">
          Dashboard
        </a>
      </div>
      <!-- Mobile hamburger -->
      <button id="hamburger" class="sm:hidden p-2 rounded-lg hover:bg-white/5 transition-colors"
              onclick="document.getElementById('mobile-menu').classList.toggle('open')">
        <svg class="w-5 h-5 text-slate-300" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
      </button>
    </nav>
    <!-- Mobile dropdown -->
    <div id="mobile-menu" class="sm:hidden border-t border-white/5 px-4 py-3 space-y-1">
      <a href="/" class="block text-sm font-medium text-slate-400 hover:text-white px-3 py-2
                          rounded-lg hover:bg-white/5 transition-all">🏠 Home</a>
      <a href="/dashboard" class="block text-sm font-semibold text-indigo-300 px-3 py-2
                                   rounded-lg bg-indigo-600/10 hover:bg-indigo-600/20 transition-all">
        📊 Dashboard
      </a>
    </div>
  </header>

  <!-- ── MAIN ── -->
  <main class="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
    {content}
  </main>

  <!-- ── FOOTER ── -->
  <footer class="border-t border-white/5 mt-20">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 py-6 flex flex-col sm:flex-row
                items-center justify-between gap-3 text-xs text-slate-600">
      <span>© 2025 {APP_NAME} — Free Lua Script CDN</span>
      <a href="https://t.me/azhxss" target="_blank"
         class="flex items-center gap-1.5 text-indigo-500 hover:text-indigo-400 transition-colors">
        <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
          <path d="M11.944 0A12 12 0 1 0 24 12 12 12 0 0 0 11.944 0zm5.59 8.158-2.05 9.658c-.154.69-.557.858-1.128.534l-3.12-2.3-1.506 1.45c-.166.167-.306.306-.626.306l.224-3.163 5.766-5.207c.252-.224-.054-.347-.39-.123L8.31 14.34l-3.062-.956c-.665-.208-.68-.665.14-.986l11.955-4.607c.556-.2 1.04.137.853.966l.338-.599z"/>
        </svg>
        @azhxss
      </a>
    </div>
  </footer>

</div>

<!-- ── TOAST ── -->
<div id="toast" class="flex items-center gap-2.5 px-4 py-3 rounded-2xl shadow-2xl
                        bg-emerald-600 text-white text-sm font-semibold min-w-[220px]
                        border border-white/10">
  <span id="toast-icon">✅</span>
  <span id="toast-msg">Copied!</span>
</div>

<script>
  // ── Toast ──
  function showToast(msg, type) {{
    const t = document.getElementById('toast');
    const icon = document.getElementById('toast-icon');
    document.getElementById('toast-msg').textContent = msg;
    if (type === 'error') {{
      t.style.background = '#dc2626';
      icon.textContent = '❌';
    }} else {{
      t.style.background = '#059669';
      icon.textContent = '✅';
    }}
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2500);
  }}

  // ── Copy by element ID ──
  function copyById(id, label) {{
    const el = document.getElementById(id);
    if (!el) return;
    const text = el.getAttribute('data-copy') || el.textContent;
    navigator.clipboard.writeText(text.trim())
      .then(() => showToast(label || 'Copied!'))
      .catch(() => {{
        // Fallback for older browsers
        const ta = document.createElement('textarea');
        ta.value = text.trim();
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast(label || 'Copied!');
      }});
  }}

  // ── Copy raw text ──
  function copyText(text, label) {{
    navigator.clipboard.writeText(text)
      .then(() => showToast(label || 'Copied!'))
      .catch(() => showToast('Copy failed — try manually', 'error'));
  }}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────
#  HOME
# ─────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    with get_conn() as conn:
        total_scripts = conn.execute("SELECT COUNT(*) FROM scripts").fetchone()[0]
        total_views   = conn.execute("SELECT COALESCE(SUM(views),0) FROM scripts").fetchone()[0]

    features = [
        ("⚡", "Instant Upload",    "Paste code or upload a .lua file — get a live CDN URL in seconds."),
        ("📋", "One-click Copy",    "Copy your loadstring instantly with a single tap. Works on mobile too."),
        ("📊", "View Tracking",     "See exactly how many times each script has been executed."),
        ("📁", "File Upload",       "Upload large .lua files directly — no more lag from pasting big scripts."),
        ("📱", "Mobile Friendly",   "Full dashboard on any screen size — phone, tablet, desktop."),
        ("☁️", "Render Free Tier", "Deployed on Render free plan — no credit card needed."),
    ]

    feat_html = "".join([
        f'<div class="glass-card rounded-2xl p-6 animate-slide-up" style="animation-delay:{i*0.05}s">'
        f'<div class="text-3xl mb-3">{icon}</div>'
        f'<h3 class="font-bold mb-2 text-sm">{ttl}</h3>'
        f'<p class="text-slate-500 text-xs leading-relaxed">{desc}</p>'
        f'</div>'
        for i, (icon, ttl, desc) in enumerate(features)
    ])

    hero = f"""
    <section class="text-center py-14 sm:py-24 animate-slide-up">
      <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full glass text-indigo-400
                  text-xs font-semibold mb-8 border border-indigo-500/20">
        <span class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse"></span>
        Free Lua Script CDN — No Login Required
      </div>

      <h1 class="text-4xl sm:text-6xl lg:text-7xl font-black tracking-tight mb-6 leading-[1.1]">
        Host Your
        <span class="bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400
                     bg-clip-text text-transparent"> Lua Scripts</span><br>
        <span class="text-slate-300">Instantly, Free</span>
      </h1>

      <p class="text-slate-400 text-base sm:text-lg max-w-lg mx-auto mb-10 leading-relaxed">
        Paste code or upload a <code class="text-indigo-400 mono text-sm">.lua</code> file.
        Get a <code class="text-indigo-400 mono text-sm">loadstring</code> URL instantly. Share with anyone.
      </p>

      <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
        <a href="/dashboard"
           class="btn-primary px-8 py-3.5 rounded-2xl text-sm w-full sm:w-auto text-center">
          🚀 Get Started Free
        </a>
        <a href="/dashboard"
           class="btn-ghost px-8 py-3.5 rounded-2xl text-sm w-full sm:w-auto text-center">
          📊 View Dashboard
        </a>
      </div>
    </section>

    <!-- Stats -->
    <section class="grid grid-cols-3 gap-3 sm:gap-6 mb-20 max-w-2xl mx-auto">
      <div class="glass-card rounded-2xl p-5 sm:p-8 text-center">
        <div class="text-2xl sm:text-4xl font-black text-indigo-400 stat-indigo mb-1">{total_scripts:,}</div>
        <div class="text-slate-500 text-xs">Scripts Hosted</div>
      </div>
      <div class="glass-card rounded-2xl p-5 sm:p-8 text-center">
        <div class="text-2xl sm:text-4xl font-black text-violet-400 stat-violet mb-1">{total_views:,}</div>
        <div class="text-slate-500 text-xs">Total Loads</div>
      </div>
      <div class="glass-card rounded-2xl p-5 sm:p-8 text-center">
        <div class="text-2xl sm:text-4xl font-black text-emerald-400 stat-emerald mb-1">Free</div>
        <div class="text-slate-500 text-xs">Always</div>
      </div>
    </section>

    <!-- Features -->
    <section class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-16">
      {feat_html}
    </section>

    <!-- CTA -->
    <section class="glass-card rounded-3xl p-8 sm:p-12 text-center mb-8">
      <h2 class="text-2xl sm:text-3xl font-black mb-3">Ready to host your script?</h2>
      <p class="text-slate-400 text-sm mb-6">No account. No credit card. Just paste and share.</p>
      <a href="/dashboard" class="btn-primary px-8 py-3.5 rounded-2xl text-sm inline-block">
        Upload Now →
      </a>
    </section>
    """
    return layout(hero, "Home")


# ─────────────────────────────────────────────
#  DASHBOARD  (public — no login)
# ─────────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, msg: str = None, err: str = None):
    with get_conn() as conn:
        scripts = conn.execute(
            "SELECT * FROM scripts ORDER BY updated_at DESC"
        ).fetchall()
        total_views = conn.execute(
            "SELECT COALESCE(SUM(views),0) FROM scripts"
        ).fetchone()[0]

    notice   = alert(msg, "success") if msg else ""
    err_html = alert(err) if err else ""

    base_url = str(request.base_url).rstrip("/")

    # Build script cards
    if scripts:
        cards = ""
        for i, s in enumerate(scripts):
            raw_url      = f"{base_url}/raw/{s['id']}"
            loadstring   = f'loadstring(game:HttpGet("{raw_url}"))();'
            card_id      = f"card_{s['id']}"
            ls_id        = f"ls_{s['id']}"
            url_id       = f"url_{s['id']}"

            cards += f"""
            <div class="glass-card rounded-2xl p-5 animate-slide-up" style="animation-delay:{i*0.04}s">
              <!-- Header row -->
              <div class="flex items-start justify-between gap-3 mb-4">
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2 flex-wrap">
                    <h3 class="font-bold text-sm text-white truncate">{s["title"]}</h3>
                    <span class="badge bg-indigo-500/15 text-indigo-400 border border-indigo-500/20">Lua</span>
                  </div>
                  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1.5">
                    <span class="mono text-slate-600 text-xs">{s["id"]}</span>
                    <span class="flex items-center gap-1 text-slate-500 text-xs">
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                        <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                      </svg>
                      {s["views"]:,} loads
                    </span>
                    <span class="text-slate-600 text-xs">{s["updated_at"][:10]}</span>
                  </div>
                </div>
                <!-- Delete -->
                <form action="/delete/{s['id']}" method="post" class="shrink-0"
                      onsubmit="return confirm('Delete &quot;{s["title"]}&quot; permanently?')">
                  <button type="submit"
                          class="p-2 rounded-xl text-slate-700 hover:text-red-400
                                 hover:bg-red-500/10 border border-transparent
                                 hover:border-red-500/20 transition-all" title="Delete script">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                  </button>
                </form>
              </div>

              <!-- Loadstring box (hidden data attribute holds real value) -->
              <div class="mb-3">
                <div class="flex items-center justify-between mb-1.5">
                  <span class="text-xs text-slate-500 font-medium">loadstring</span>
                  <span class="text-xs text-slate-600 mono">{raw_url.replace(base_url, '')}</span>
                </div>
                <div id="{ls_id}"
                     data-copy='{loadstring}'
                     class="loadstring-box select-none"
                     onclick="copyById('{ls_id}', 'Loadstring copied! ✅')"
                     title="Click to copy">
                  <span class="text-violet-400">loadstring</span>(<span class="text-emerald-400">game</span>:<span class="text-blue-400">HttpGet</span>(<span class="text-amber-300">"{raw_url}"</span>))();
                </div>
              </div>

              <!-- Hidden raw URL element -->
              <span id="{url_id}" data-copy="{raw_url}" class="hidden"></span>

              <!-- Action buttons -->
              <div class="flex gap-2 flex-wrap">
                <button onclick="copyById('{ls_id}', 'Loadstring copied!')"
                        class="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold
                               py-2.5 px-3 rounded-xl bg-indigo-600/15 hover:bg-indigo-600/25
                               text-indigo-400 border border-indigo-500/20 hover:border-indigo-500/40
                               transition-all min-w-[120px]">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round"
                          d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                  </svg>
                  Copy Loadstring
                </button>
                <button onclick="copyById('{url_id}', 'Raw URL copied!')"
                        class="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold
                               py-2.5 px-3 rounded-xl btn-ghost transition-all min-w-[100px]">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round"
                          d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
                  </svg>
                  Copy URL
                </button>
                <a href="/raw/{s['id']}" target="_blank"
                   class="flex items-center justify-center gap-1.5 text-xs font-semibold
                          py-2.5 px-3 rounded-xl btn-ghost transition-all">
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round"
                          d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                  </svg>
                  View Raw
                </a>
              </div>
            </div>"""
    else:
        cards = """
        <div class="glass-card rounded-2xl p-14 text-center col-span-full">
          <div class="text-5xl mb-4">📭</div>
          <p class="text-slate-400 font-semibold mb-1">No scripts yet</p>
          <p class="text-slate-600 text-sm">Upload your first Lua script using the panel on the left.</p>
        </div>"""

    summary = f"""
    <div class="grid grid-cols-3 gap-3 mb-8">
      <div class="glass-card rounded-2xl p-4 text-center">
        <div class="text-2xl font-black text-indigo-400 stat-indigo">{len(scripts)}</div>
        <div class="text-slate-500 text-xs mt-0.5">Scripts</div>
      </div>
      <div class="glass-card rounded-2xl p-4 text-center">
        <div class="text-2xl font-black text-violet-400 stat-violet">{total_views:,}</div>
        <div class="text-slate-500 text-xs mt-0.5">Total Loads</div>
      </div>
      <div class="glass-card rounded-2xl p-4 text-center">
        <div class="text-2xl font-black text-emerald-400 stat-emerald">CDN</div>
        <div class="text-slate-500 text-xs mt-0.5">Hosted</div>
      </div>
    </div>"""

    content = f"""
    <div class="mb-8 animate-slide-up">
      <h1 class="text-2xl sm:text-3xl font-black mb-1">
        Script <span class="logo-text">Dashboard</span>
      </h1>
      <p class="text-slate-500 text-sm">Upload scripts and get a loadstring URL instantly.</p>
    </div>

    {notice}{err_html}
    {summary}

    <div class="grid lg:grid-cols-3 gap-6">

      <!-- ── Upload Panel ── -->
      <div class="lg:col-span-1">
        <div class="glass-card rounded-2xl p-6 sticky top-20">
          <h2 class="font-bold mb-5 flex items-center gap-2 text-sm">
            <span class="w-6 h-6 rounded-lg bg-indigo-600/20 text-indigo-400
                         flex items-center justify-center text-xs font-black">+</span>
            New Script
          </h2>

          <!-- Tabs -->
          <div class="flex gap-1 p-1 bg-white/5 rounded-xl mb-5 border border-white/5">
            <button id="tab-paste" onclick="switchTab('paste')"
                    class="tab-btn active flex-1 text-xs font-semibold py-2 rounded-lg border border-transparent">
              ✏️ Paste Code
            </button>
            <button id="tab-file" onclick="switchTab('file')"
                    class="tab-btn flex-1 text-xs font-semibold py-2 rounded-lg border border-transparent
                           text-slate-500">
              📁 Upload File
            </button>
          </div>

          <!-- Paste tab -->
          <form id="form-paste" action="/upload" method="post" class="space-y-4">
            <div>
              <label class="text-xs font-semibold text-slate-400 mb-1.5 block">Script Name</label>
              <input name="title" placeholder="My awesome script" required
                     class="w-full rounded-xl px-3 py-2.5 text-sm">
            </div>
            <div>
              <label class="text-xs font-semibold text-slate-400 mb-1.5 block">Lua Code</label>
              <textarea name="content" rows="10" required
                        placeholder="-- paste your Lua code here&#10;print('Hello Roblox!')"
                        class="w-full rounded-xl px-3 py-2.5 text-xs mono resize-y"></textarea>
            </div>
            <button type="submit" class="btn-primary w-full py-3 rounded-xl text-sm">
              Upload Script ↑
            </button>
          </form>

          <!-- File Upload tab -->
          <form id="form-file" action="/upload-file" method="post"
                enctype="multipart/form-data" class="space-y-4 hidden">
            <div>
              <label class="text-xs font-semibold text-slate-400 mb-1.5 block">Script Name</label>
              <input name="title" placeholder="My awesome script"
                     class="w-full rounded-xl px-3 py-2.5 text-sm">
              <p class="text-xs text-slate-600 mt-1">Leave blank to use filename</p>
            </div>
            <div>
              <label class="text-xs font-semibold text-slate-400 mb-1.5 block">.lua File</label>
              <div class="drop-zone p-6 text-center" id="drop-zone"
                   onclick="document.getElementById('file-input').click()">
                <input type="file" name="file" id="file-input" accept=".lua,.txt"
                       class="hidden" onchange="onFileSelected(this)">
                <div id="drop-label">
                  <div class="text-3xl mb-2">📂</div>
                  <p class="text-slate-400 text-xs font-semibold mb-1">Click to browse</p>
                  <p class="text-slate-600 text-xs">or drag & drop a .lua file here</p>
                </div>
                <div id="file-selected" class="hidden">
                  <div class="text-2xl mb-2">✅</div>
                  <p id="file-name" class="text-emerald-400 text-xs font-semibold"></p>
                  <p id="file-size" class="text-slate-500 text-xs mt-0.5"></p>
                </div>
              </div>
            </div>
            <button type="submit" class="btn-primary w-full py-3 rounded-xl text-sm">
              Upload File ↑
            </button>
          </form>

          <p class="text-xs text-slate-600 mt-4 text-center leading-relaxed">
            Supports any size Lua script — no lag on copy
          </p>
        </div>
      </div>

      <!-- ── Script List ── -->
      <div class="lg:col-span-2">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-bold text-sm">Hosted Scripts</h2>
          <span class="text-xs text-slate-600 bg-white/5 px-2.5 py-1 rounded-full
                        border border-white/5">{len(scripts)} total</span>
        </div>
        <div class="space-y-3">
          {cards}
        </div>
      </div>

    </div>

    <script>
      // ── Tab switching ──
      function switchTab(tab) {{
        const isPaste = tab === 'paste';
        document.getElementById('form-paste').classList.toggle('hidden', !isPaste);
        document.getElementById('form-file').classList.toggle('hidden', isPaste);
        document.getElementById('tab-paste').classList.toggle('active', isPaste);
        document.getElementById('tab-paste').classList.toggle('text-slate-500', !isPaste);
        document.getElementById('tab-file').classList.toggle('active', !isPaste);
        document.getElementById('tab-file').classList.toggle('text-slate-500', isPaste);
      }}

      // ── File selected display ──
      function onFileSelected(input) {{
        if (!input.files.length) return;
        const file = input.files[0];
        const mb = (file.size / 1024 / 1024).toFixed(2);
        document.getElementById('drop-label').classList.add('hidden');
        document.getElementById('file-selected').classList.remove('hidden');
        document.getElementById('file-name').textContent = file.name;
        document.getElementById('file-size').textContent = mb + ' MB';
      }}

      // ── Drag & drop ──
      const dz = document.getElementById('drop-zone');
      if (dz) {{
        dz.addEventListener('dragover', (e) => {{ e.preventDefault(); dz.classList.add('dragover'); }});
        dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
        dz.addEventListener('drop', (e) => {{
          e.preventDefault();
          dz.classList.remove('dragover');
          const fi = document.getElementById('file-input');
          fi.files = e.dataTransfer.files;
          onFileSelected(fi);
        }});
      }}
    </script>
    """
    return layout(content, "Dashboard")


# ─────────────────────────────────────────────
#  UPLOAD — paste text
# ─────────────────────────────────────────────
@app.post("/upload")
async def upload(title: str = Form(...), content: str = Form(...)):
    if not title.strip() or not content.strip():
        return RedirectResponse("/dashboard?err=Title+and+content+are+required", status_code=303)

    sid = gen_id(10)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO scripts (id, title, updated_at) VALUES (?,?,?)",
            (sid, title.strip(), now)
        )
        conn.execute(
            "INSERT INTO versions (script_id, content, v) VALUES (?,?,1)",
            (sid, content)
        )

    return RedirectResponse("/dashboard?msg=Script+uploaded+successfully!", status_code=303)


# ─────────────────────────────────────────────
#  UPLOAD FILE — .lua file upload
# ─────────────────────────────────────────────
@app.post("/upload-file")
async def upload_file(title: str = Form(""), file: UploadFile = File(...)):
    raw = await file.read()

    # Try to decode
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            content = raw.decode("latin-1")
        except Exception:
            return RedirectResponse("/dashboard?err=Could+not+read+file+encoding", status_code=303)

    if not content.strip():
        return RedirectResponse("/dashboard?err=Uploaded+file+is+empty", status_code=303)

    # Use filename as title if not provided
    script_title = title.strip() or file.filename.replace(".lua", "").replace("_", " ").replace("-", " ").strip()
    if not script_title:
        script_title = "Untitled Script"

    sid = gen_id(10)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO scripts (id, title, updated_at) VALUES (?,?,?)",
            (sid, script_title, now)
        )
        conn.execute(
            "INSERT INTO versions (script_id, content, v) VALUES (?,?,1)",
            (sid, content)
        )

    return RedirectResponse("/dashboard?msg=File+uploaded+successfully!", status_code=303)


# ─────────────────────────────────────────────
#  RAW  (serve plain Lua — tracks views)
# ─────────────────────────────────────────────
@app.get("/raw/{script_id}", response_class=PlainTextResponse)
async def raw(script_id: str):
    with get_conn() as conn:
        script = conn.execute(
            "SELECT * FROM scripts WHERE id=?", (script_id,)
        ).fetchone()
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        ver = conn.execute(
            "SELECT content FROM versions WHERE script_id=? ORDER BY v DESC LIMIT 1",
            (script_id,)
        ).fetchone()
        if not ver:
            raise HTTPException(status_code=404, detail="No content found")

        conn.execute("UPDATE scripts SET views=views+1 WHERE id=?", (script_id,))

    return PlainTextResponse(ver["content"], media_type="text/plain; charset=utf-8")


# ─────────────────────────────────────────────
#  DELETE
# ─────────────────────────────────────────────
@app.post("/delete/{script_id}")
async def delete_script(script_id: str):
    with get_conn() as conn:
        script = conn.execute(
            "SELECT id FROM scripts WHERE id=?", (script_id,)
        ).fetchone()
        if not script:
            return RedirectResponse("/dashboard?err=Script+not+found", status_code=303)
        conn.execute("DELETE FROM scripts WHERE id=?", (script_id,))
        conn.execute("DELETE FROM versions WHERE script_id=?", (script_id,))

    return RedirectResponse("/dashboard?msg=Script+deleted", status_code=303)


# ─────────────────────────────────────────────
#  HEALTH CHECK  (Render keep-alive)
# ─────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "app": APP_NAME}


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
