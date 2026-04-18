import os
import sqlite3
import random
import string
import secrets
import base64
from datetime import datetime
from fastapi import FastAPI, Request, Form, HTTPException
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

def obfuscate_url(url: str) -> str:
    """
    Encodes the raw URL into a Lua loadstring that decodes at runtime.
    The real URL is hidden — Base64 encoded and decoded inside Lua itself.
    Result looks like:
      loadstring(game:HttpGet(({...})[1]))()
    with the URL split into base64 char-code chunks.
    """
    b64 = base64.b64encode(url.encode()).decode()
    # Split into 4-char chunks for visual obfuscation
    chunks = [b64[i:i+4] for i in range(0, len(b64), 4)]
    lua_table = "{" + ",".join(f'"{c}"' for c in chunks) + "}"
    # Lua snippet that rebuilds the URL at runtime:
    #   local t={...} local s="" for _,v in ipairs(t) do s=s..v end
    #   then base64-decode via a pure-Lua b64 decoder, then HttpGet
    lua_b64decode = (
        "local b='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'"
        " local t=" + lua_table +
        " local s='' for _,v in ipairs(t) do s=s..v end"
        " local d='' s=s:gsub('[^'..b..'=]','')"
        " for i=1,#s,4 do"
        " local a,e,f,g=s:sub(i,i),s:sub(i+1,i+1),s:sub(i+2,i+2),s:sub(i+3,i+3)"
        " local n=(b:find(a)-1)*262144+(b:find(e)-1)*4096"
        " if f~='=' then n=n+(b:find(f)-1)*64 end"
        " if g~='=' then n=n+(b:find(g)-1) end"
        " d=d..string.char(math.floor(n/65536))"
        " if f~='=' then d=d..string.char(math.floor((n%65536)/256)) end"
        " if g~='=' then d=d..string.char(n%256) end"
        " end"
        " return d"
    )
    obfuscated = f"loadstring(game:HttpGet((function() {lua_b64decode} end)()))()"
    return obfuscated

def alert(msg: str, kind: str = "error") -> str:
    color = "red" if kind == "error" else "indigo" if kind == "info" else "emerald"
    icon  = "⚠" if kind == "error" else "ℹ" if kind == "info" else "✓"
    return f"""
    <div class="flex items-center gap-3 mb-5 px-4 py-3 rounded-xl border
        bg-{color}-500/10 border-{color}-500/30 text-{color}-300 text-sm">
        <span class="text-lg">{icon}</span> {msg}
    </div>"""


# ─────────────────────────────────────────────
#  BASE LAYOUT  (no auth nav — fully public)
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
      background: #030712;
      color: #f1f5f9;
      min-height: 100dvh;
    }}
    .mono {{ font-family: 'JetBrains Mono', monospace; }}

    body::before {{
      content: '';
      position: fixed;
      inset: 0;
      background:
        radial-gradient(ellipse 80% 60% at 10% 0%, rgba(99,102,241,.18) 0%, transparent 60%),
        radial-gradient(ellipse 60% 50% at 90% 100%, rgba(139,92,246,.12) 0%, transparent 60%);
      pointer-events: none;
      z-index: 0;
    }}

    .glass {{
      background: rgba(255,255,255,.03);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255,255,255,.07);
    }}
    .glass-card {{
      background: rgba(255,255,255,.025);
      border: 1px solid rgba(255,255,255,.07);
      transition: border-color .2s, background .2s;
    }}
    .glass-card:hover {{
      background: rgba(255,255,255,.04);
      border-color: rgba(99,102,241,.35);
    }}

    input, textarea {{
      background: rgba(255,255,255,.04) !important;
      border: 1px solid rgba(255,255,255,.1) !important;
      color: #f1f5f9 !important;
      outline: none !important;
      transition: border-color .2s !important;
    }}
    input::placeholder, textarea::placeholder {{
      color: #475569 !important;
    }}
    input:focus, textarea:focus {{
      border-color: #6366f1 !important;
      box-shadow: 0 0 0 2px rgba(99,102,241,.15) !important;
    }}

    .btn-primary {{
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      color: white;
      font-weight: 600;
      transition: opacity .2s, transform .1s;
    }}
    .btn-primary:hover {{ opacity: .92; transform: translateY(-1px); }}
    .btn-primary:active {{ transform: translateY(0); }}

    .logo-glow {{
      text-shadow: 0 0 30px rgba(99,102,241,.6), 0 0 60px rgba(99,102,241,.2);
    }}

    .obf-box {{
      background: #0f172a;
      border: 1px solid rgba(99,102,241,.3);
      border-radius: .75rem;
      padding: .75rem 1rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: .65rem;
      color: #a5b4fc;
      word-break: break-all;
      cursor: pointer;
      position: relative;
      line-height: 1.6;
      max-height: 80px;
      overflow: hidden;
    }}
    .obf-box::after {{
      content: '';
      position: absolute;
      bottom: 0; left: 0; right: 0;
      height: 28px;
      background: linear-gradient(transparent, #0f172a);
    }}
    .obf-box:hover {{ border-color: rgba(99,102,241,.6); }}

    #toast {{
      position: fixed; bottom: 1.5rem; right: 1.5rem;
      transform: translateY(4rem); opacity: 0;
      transition: all .35s cubic-bezier(.34,1.56,.64,1);
      z-index: 1000;
    }}
    #toast.show {{ transform: translateY(0); opacity: 1; }}

    ::-webkit-scrollbar {{ width: 6px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
  </style>
</head>
<body class="relative z-10">

  <!-- ── NAV ── -->
  <header class="sticky top-0 z-50 border-b border-white/5 glass">
    <nav class="max-w-6xl mx-auto flex items-center justify-between px-4 sm:px-6 h-14">
      <a href="/" class="flex items-center gap-2 shrink-0">
        <div class="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-xs font-black">S</div>
        <span class="font-bold text-base tracking-tight logo-glow">{APP_NAME}</span>
      </a>
      <div class="flex items-center gap-3">
        <a href="/"
           class="text-sm font-medium text-slate-300 hover:text-indigo-400 transition-colors">
          Home
        </a>
        <a href="/dashboard"
           class="text-sm font-medium bg-indigo-600 hover:bg-indigo-500
                  text-white px-4 py-2 rounded-lg transition-colors">
          Dashboard
        </a>
      </div>
    </nav>
  </header>

  <!-- ── MAIN ── -->
  <main class="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
    {content}
  </main>

  <!-- ── FOOTER ── -->
  <footer class="border-t border-white/5 mt-16">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 py-6 flex flex-col sm:flex-row
                items-center justify-between gap-3 text-xs text-slate-600">
      <span>© 2025 {APP_NAME}. Free Lua CDN Hosting.</span>
      <a href="https://t.me/azhxss" class="text-indigo-500 hover:text-indigo-400 transition-colors">
        Telegram @azhxss
      </a>
    </div>
  </footer>

  <!-- ── TOAST ── -->
  <div id="toast"
       class="flex items-center gap-2 px-4 py-3 rounded-xl shadow-2xl
              bg-indigo-600 text-white text-sm font-medium min-w-[200px]">
    <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
    </svg>
    <span id="toast-msg">Copied!</span>
  </div>

  <script>
    function showToast(msg = 'Copied!') {{
      const t = document.getElementById('toast');
      document.getElementById('toast-msg').textContent = msg;
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 2500);
    }}
    function copyText(text, label = 'Copied!') {{
      navigator.clipboard.writeText(text).then(() => showToast(label));
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

    hero = f"""
    <section class="text-center py-16 sm:py-24">
      <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full glass text-indigo-400
                  text-xs font-semibold mb-8 border border-indigo-500/20">
        <span class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse"></span>
        Free Lua Script CDN — No Login Required
      </div>

      <h1 class="text-4xl sm:text-6xl lg:text-7xl font-black tracking-tight mb-6 leading-tight">
        Host Your
        <span class="bg-gradient-to-r from-indigo-400 to-violet-400
                     bg-clip-text text-transparent"> Lua Scripts</span><br>
        Instantly, Free
      </h1>

      <p class="text-slate-400 text-base sm:text-lg max-w-xl mx-auto mb-10 leading-relaxed">
        Paste your Lua code. Get an obfuscated <code class="text-indigo-400 mono text-sm">loadstring</code> instantly.
        No account, no setup — just host and share.
      </p>

      <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
        <a href="/dashboard"
           class="btn-primary px-7 py-3 rounded-xl text-sm w-full sm:w-auto text-center">
          Upload a Script →
        </a>
      </div>
    </section>

    <section class="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-6 mb-20">
      <div class="glass-card rounded-2xl p-5 sm:p-8 text-center">
        <div class="text-2xl sm:text-4xl font-black text-indigo-400 mb-1">{total_scripts:,}</div>
        <div class="text-slate-500 text-xs sm:text-sm">Scripts Hosted</div>
      </div>
      <div class="glass-card rounded-2xl p-5 sm:p-8 text-center">
        <div class="text-2xl sm:text-4xl font-black text-violet-400 mb-1">{total_views:,}</div>
        <div class="text-slate-500 text-xs sm:text-sm">Total Loads</div>
      </div>
      <div class="col-span-2 sm:col-span-1 glass-card rounded-2xl p-5 sm:p-8 text-center">
        <div class="text-2xl sm:text-4xl font-black text-emerald-400 mb-1">Free</div>
        <div class="text-slate-500 text-xs sm:text-sm">Always</div>
      </div>
    </section>

    <section class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-16">
      {"".join([
        f'<div class="glass-card rounded-2xl p-6">'
        f'<div class="text-2xl mb-3">{icon}</div>'
        f'<h3 class="font-bold mb-2">{ttl}</h3>'
        f'<p class="text-slate-400 text-sm leading-relaxed">{desc}</p>'
        f'</div>'
        for icon, ttl, desc in [
            ("⚡", "Instant Upload",      "Paste your script and get a live CDN URL in seconds. Zero friction."),
            ("🔐", "Obfuscated Loadstring","The raw URL is hidden inside a Lua decoder — not visible in plain text."),
            ("📊", "View Tracking",       "See exactly how many times each script has been executed."),
            ("🔗", "One-click Copy",      "Copy the full obfuscated loadstring to clipboard instantly."),
            ("📱", "Mobile Friendly",     "Full dashboard on any screen size — phone, tablet, desktop."),
            ("☁️", "Render Free Tier",   "Deployed on Render free plan — no credit card, no limits."),
        ]
      ])}
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

    # Script cards
    if scripts:
        cards = ""
        for s in scripts:
            raw_url  = f"{base_url}/raw/{s['id']}"
            obf_code = obfuscate_url(raw_url)
            cards += f"""
            <div class="glass-card rounded-2xl p-5">
              <!-- header -->
              <div class="flex items-start justify-between gap-2 mb-3">
                <div class="min-w-0">
                  <h3 class="font-semibold truncate text-sm">{s['title']}</h3>
                  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1">
                    <span class="text-slate-600 text-xs mono">{s['id']}</span>
                    <span class="text-slate-500 text-xs">👁 {s['views']:,} loads</span>
                    <span class="text-slate-600 text-xs">{s['updated_at'][:10]}</span>
                  </div>
                </div>
                <!-- delete -->
                <form action="/delete/{s['id']}" method="post" class="shrink-0"
                      onsubmit="return confirm('Delete this script permanently?')">
                  <button class="text-slate-700 hover:text-red-400 p-1.5 rounded-lg
                                 hover:bg-red-500/10 transition-colors" title="Delete script">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                  </button>
                </form>
              </div>

              <!-- obfuscated loadstring preview box -->
              <div class="obf-box mb-3" onclick="copyText(`{obf_code}`, 'Obfuscated loadstring copied!')"
                   title="Click to copy obfuscated loadstring">
                {obf_code}
              </div>

              <!-- badge -->
              <div class="flex items-center gap-1.5 mb-3">
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md
                             bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs font-medium">
                  🔐 URL obfuscated
                </span>
              </div>

              <!-- action buttons -->
              <div class="flex flex-wrap gap-2">
                <button onclick="copyText(`{obf_code}`, 'Obfuscated loadstring copied!')"
                        class="flex-1 text-xs font-semibold py-2 px-3 rounded-lg
                               bg-indigo-600/15 hover:bg-indigo-600/25 text-indigo-400
                               border border-indigo-500/20 transition-colors">
                  Copy Loadstring
                </button>
                <button onclick="copyText('{raw_url}', 'Raw URL copied!')"
                        class="flex-1 text-xs font-semibold py-2 px-3 rounded-lg
                               glass hover:bg-white/5 text-slate-300 transition-colors">
                  Copy Raw URL
                </button>
                <a href="/raw/{s['id']}" target="_blank"
                   class="text-xs font-semibold py-2 px-3 rounded-lg
                          glass hover:bg-white/5 text-slate-400 transition-colors">
                  View Raw
                </a>
              </div>
            </div>"""
    else:
        cards = """
        <div class="glass-card rounded-2xl p-10 text-center col-span-full">
          <div class="text-4xl mb-3">📭</div>
          <p class="text-slate-500 text-sm">No scripts yet. Upload your first one!</p>
        </div>"""

    summary = f"""
    <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-8">
      <div class="glass-card rounded-xl p-4 text-center">
        <div class="text-2xl font-black text-indigo-400">{len(scripts)}</div>
        <div class="text-slate-500 text-xs mt-0.5">Scripts</div>
      </div>
      <div class="glass-card rounded-xl p-4 text-center">
        <div class="text-2xl font-black text-violet-400">{total_views:,}</div>
        <div class="text-slate-500 text-xs mt-0.5">Total Loads</div>
      </div>
      <div class="col-span-2 sm:col-span-1 glass-card rounded-xl p-4 text-center">
        <div class="text-2xl font-black text-emerald-400">🔐</div>
        <div class="text-slate-500 text-xs mt-0.5">Obfuscated URLs</div>
      </div>
    </div>"""

    content = f"""
    <div class="mb-8">
      <h1 class="text-2xl sm:text-3xl font-black mb-1">
        Script <span class="text-indigo-400">Dashboard</span>
      </h1>
      <p class="text-slate-500 text-sm">Upload scripts — get obfuscated loadstrings instantly. No login needed.</p>
    </div>

    {notice}{err_html}
    {summary}

    <div class="grid lg:grid-cols-3 gap-6">

      <!-- Upload Panel -->
      <div class="lg:col-span-1">
        <div class="glass-card rounded-2xl p-6 sticky top-20">
          <h2 class="font-bold mb-4 flex items-center gap-2">
            <span class="w-6 h-6 rounded-md bg-indigo-600/20 text-indigo-400
                         flex items-center justify-center text-xs">+</span>
            Upload Script
          </h2>
          <form action="/upload" method="post" class="space-y-3">
            <div>
              <label class="text-xs font-medium text-slate-400 mb-1.5 block">Script Name</label>
              <input name="title" placeholder="My awesome script" required
                     class="w-full rounded-xl px-3 py-2.5 text-sm">
            </div>
            <div>
              <label class="text-xs font-medium text-slate-400 mb-1.5 block">Lua Code</label>
              <textarea name="content" rows="10" required
                        placeholder="-- paste your Lua code here"
                        class="w-full rounded-xl px-3 py-2.5 text-xs mono resize-none"></textarea>
            </div>
            <button type="submit" class="btn-primary w-full py-3 rounded-xl text-sm">
              Upload &amp; Obfuscate ↑
            </button>
          </form>
          <p class="text-xs text-slate-600 mt-3 text-center leading-relaxed">
            🔐 Your raw URL will be hidden inside an obfuscated Lua decoder
          </p>
        </div>
      </div>

      <!-- Script List -->
      <div class="lg:col-span-2">
        <h2 class="font-bold mb-4 flex items-center justify-between">
          <span>Hosted Scripts</span>
          <span class="text-xs text-slate-600 font-normal">{len(scripts)} total</span>
        </h2>
        <div class="space-y-3">
          {cards}
        </div>
      </div>

    </div>
    """
    return layout(content, "Dashboard")


# ─────────────────────────────────────────────
#  UPLOAD  (public)
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

    return RedirectResponse("/dashboard?msg=Script+uploaded+%26+obfuscated!", status_code=303)


# ─────────────────────────────────────────────
#  RAW  (serve plain Lua — hits are tracked)
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
#  DELETE  (public — anyone with the page can delete)
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
