import os
import sqlite3
import random
import string
import secrets
import hashlib
from datetime import datetime
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware

# ─────────────────────────────────────────────
#  CONFIG & DATABASE
# ─────────────────────────────────────────────
DB_PATH    = os.environ.get("DB_PATH", "scripthost.db")
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
APP_NAME   = "ScriptHost"
ACCENT     = "#6366f1"   # indigo-500

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS scripts (
                id         TEXT PRIMARY KEY,
                title      TEXT NOT NULL,
                owner      TEXT NOT NULL,
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
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=604800)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def gen_id(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

def get_user(request: Request) -> str | None:
    return request.session.get("user")

def require_user(request: Request) -> str:
    user = get_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return user

def alert(msg: str, kind: str = "error") -> str:
    color = "red" if kind == "error" else "indigo" if kind == "info" else "emerald"
    icon  = "⚠" if kind == "error" else "ℹ" if kind == "info" else "✓"
    return f"""
    <div class="flex items-center gap-3 mb-5 px-4 py-3 rounded-xl border
        bg-{color}-500/10 border-{color}-500/30 text-{color}-300 text-sm">
        <span class="text-lg">{icon}</span> {msg}
    </div>"""


# ─────────────────────────────────────────────
#  BASE LAYOUT (fully mobile-responsive)
# ─────────────────────────────────────────────
def layout(content: str, user: str = None, title: str = APP_NAME) -> str:
    if user:
        nav_links = f"""
        <a href="/dashboard"
           class="text-sm font-medium text-slate-300 hover:text-indigo-400 transition-colors">
           Dashboard
        </a>
        <a href="/logout"
           class="text-sm font-medium bg-red-500/10 hover:bg-red-500/20
                  text-red-400 border border-red-500/20 px-3 py-1.5 rounded-lg transition-colors">
           Logout
        </a>"""
    else:
        nav_links = f"""
        <a href="/login"
           class="text-sm font-medium text-slate-300 hover:text-indigo-400 transition-colors">
           Login
        </a>
        <a href="/register"
           class="text-sm font-medium bg-indigo-600 hover:bg-indigo-500
                  text-white px-4 py-2 rounded-lg transition-colors">
           Sign Up
        </a>"""

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

    /* gradient mesh background */
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

    input, textarea, select {{
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

    /* mobile hamburger nav */
    #mobile-menu {{ display: none; }}
    #mobile-menu.open {{ display: flex; }}

    /* toast */
    #toast {{
      position: fixed; bottom: 1.5rem; right: 1.5rem;
      transform: translateY(4rem); opacity: 0;
      transition: all .35s cubic-bezier(.34,1.56,.64,1);
      z-index: 1000;
    }}
    #toast.show {{ transform: translateY(0); opacity: 1; }}

    /* code badge */
    .loadstring-box {{
      background: #0f172a;
      border: 1px solid rgba(99,102,241,.3);
      border-radius: .75rem;
      padding: .75rem 1rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: .7rem;
      color: #a5b4fc;
      word-break: break-all;
      cursor: pointer;
    }}
    .loadstring-box:hover {{ border-color: rgba(99,102,241,.6); }}

    /* scrollbar */
    ::-webkit-scrollbar {{ width: 6px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
  </style>
</head>
<body class="relative z-10">

  <!-- ── NAV ── -->
  <header class="sticky top-0 z-50 border-b border-white/5 glass">
    <nav class="max-w-6xl mx-auto flex items-center justify-between px-4 sm:px-6 h-14">

      <!-- Logo -->
      <a href="/" class="flex items-center gap-2 shrink-0">
        <div class="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-xs font-black">S</div>
        <span class="font-bold text-base tracking-tight logo-glow">{APP_NAME}</span>
      </a>

      <!-- Desktop links -->
      <div class="hidden sm:flex items-center gap-4">
        {nav_links}
      </div>

      <!-- Mobile burger -->
      <button onclick="toggleMenu()" class="sm:hidden text-slate-400 hover:text-white p-1" aria-label="Menu">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path id="burger-icon" stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
      </button>
    </nav>

    <!-- Mobile dropdown -->
    <div id="mobile-menu"
         class="sm:hidden flex-col gap-2 px-4 pb-3 border-t border-white/5 pt-3">
      {nav_links.replace('text-sm font-medium', 'text-sm font-medium w-full text-center py-2 rounded-lg glass-card')}
    </div>
  </header>

  <!-- ── MAIN ── -->
  <main class="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
    {content}
  </main>

  <!-- ── FOOTER ── -->
  <footer class="border-t border-white/5 mt-16">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 py-6 flex flex-col sm:flex-row
                items-center justify-between gap-3 text-xs text-slate-600">
      <span>© 2025 {APP_NAME}. Lua CDN Hosting.</span>
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
    // Mobile nav
    function toggleMenu() {{
      const m = document.getElementById('mobile-menu');
      m.classList.toggle('open');
    }}

    // Toast helper
    function showToast(msg = 'Copied!') {{
      const t = document.getElementById('toast');
      document.getElementById('toast-msg').textContent = msg;
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 2500);
    }}

    // Copy loadstring
    function copyLoadstring(id) {{
      const url  = window.location.origin + '/raw/' + id;
      const code = 'loadstring(game:HttpGet("' + url + '"))()';
      navigator.clipboard.writeText(code).then(() => showToast('Loadstring copied!'));
    }}

    // Copy raw URL
    function copyRawUrl(id) {{
      const url = window.location.origin + '/raw/' + id;
      navigator.clipboard.writeText(url).then(() => showToast('Raw URL copied!'));
    }}

    // Click-to-copy loadstring boxes
    document.querySelectorAll('.loadstring-box').forEach(el => {{
      el.addEventListener('click', () => {{
        navigator.clipboard.writeText(el.textContent.trim())
          .then(() => showToast('Copied!'));
      }});
    }});
  </script>
</body>
</html>"""


# ─────────────────────────────────────────────
#  HOME
# ─────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = get_user(request)

    # live stats
    with get_conn() as conn:
        total_scripts = conn.execute("SELECT COUNT(*) FROM scripts").fetchone()[0]
        total_users   = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_views   = conn.execute("SELECT COALESCE(SUM(views),0) FROM scripts").fetchone()[0]

    hero = f"""
    <!-- Hero -->
    <section class="text-center py-16 sm:py-24">
      <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full glass text-indigo-400
                  text-xs font-semibold mb-8 border border-indigo-500/20">
        <span class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse"></span>
        Free Lua / Script CDN Hosting
      </div>

      <h1 class="text-4xl sm:text-6xl lg:text-7xl font-black tracking-tight mb-6 leading-tight">
        Host Your
        <span class="bg-gradient-to-r from-indigo-400 to-violet-400
                     bg-clip-text text-transparent"> Lua Scripts</span><br>
        With One Click
      </h1>

      <p class="text-slate-400 text-base sm:text-lg max-w-xl mx-auto mb-10 leading-relaxed">
        Instant loadstring CDN for Roblox. Upload, manage & share scripts with
        auto-versioning, view tracking and a clean dashboard.
      </p>

      <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
        <a href="/register"
           class="btn-primary px-7 py-3 rounded-xl text-sm w-full sm:w-auto text-center">
          Get Started Free →
        </a>
        <a href="/login"
           class="glass px-7 py-3 rounded-xl text-sm font-semibold text-slate-300
                  hover:text-white transition-colors w-full sm:w-auto text-center">
          Sign In
        </a>
      </div>
    </section>

    <!-- Stats -->
    <section class="grid grid-cols-3 gap-3 sm:gap-6 mb-20">
      {"".join([
        f'<div class="glass-card rounded-2xl p-5 sm:p-8 text-center">'
        f'<div class="text-2xl sm:text-4xl font-black text-indigo-400 mb-1">{v:,}</div>'
        f'<div class="text-slate-500 text-xs sm:text-sm">{lbl}</div>'
        f'</div>'
        for v, lbl in [
            (total_scripts, "Scripts Hosted"),
            (total_views,   "Total Views"),
            (total_users,   "Developers"),
        ]
      ])}
    </section>

    <!-- Features -->
    <section class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-16">
      {"".join([
        f'<div class="glass-card rounded-2xl p-6">'
        f'<div class="text-2xl mb-3">{icon}</div>'
        f'<h3 class="font-bold mb-2">{title}</h3>'
        f'<p class="text-slate-400 text-sm leading-relaxed">{desc}</p>'
        f'</div>'
        for icon, title, desc in [
            ("⚡", "Instant Hosting",     "Upload your script and get a live raw URL in seconds."),
            ("🔗", "Loadstring Ready",    "One-click copy of the full loadstring for Roblox."),
            ("📊", "View Analytics",      "Track how many times each script has been fetched."),
            ("🔒", "Auto Versioning",     "Every upload creates a new version, older content preserved."),
            ("📱", "Mobile Friendly",     "Full dashboard experience on any device, any screen size."),
            ("☁️", "Render Free Tier",   "Deploy on Render's free plan — no credit card needed."),
        ]
      ])}
    </section>
    """
    return layout(hero, user, "Home")


# ─────────────────────────────────────────────
#  AUTH — REGISTER
# ─────────────────────────────────────────────
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, err: str = None):
    user = get_user(request)
    if user:
        return RedirectResponse("/dashboard")
    err_html = alert(err) if err else ""
    body = f"""
    <div class="max-w-md mx-auto">
      <div class="glass-card rounded-3xl p-8">
        <div class="flex items-center gap-3 mb-8">
          <div class="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30
                      flex items-center justify-center text-lg">✨</div>
          <div>
            <h2 class="text-xl font-bold">Create Account</h2>
            <p class="text-slate-500 text-xs">Free, no credit card required</p>
          </div>
        </div>
        {err_html}
        <form action="/register" method="post" class="space-y-4">
          <div>
            <label class="text-xs font-medium text-slate-400 mb-1.5 block">Username</label>
            <input name="username" placeholder="your_username" required
                   class="w-full rounded-xl px-4 py-3 text-sm">
          </div>
          <div>
            <label class="text-xs font-medium text-slate-400 mb-1.5 block">Password</label>
            <input name="password" type="password" placeholder="••••••••" required
                   class="w-full rounded-xl px-4 py-3 text-sm">
          </div>
          <button type="submit" class="btn-primary w-full py-3 rounded-xl text-sm mt-2">
            Create Account
          </button>
        </form>
        <p class="text-center text-xs text-slate-600 mt-5">
          Already have an account?
          <a href="/login" class="text-indigo-400 hover:text-indigo-300">Sign In</a>
        </p>
      </div>
    </div>"""
    return layout(body, title="Register")


@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...)):
    if len(username) < 3:
        return RedirectResponse("/register?err=Username+must+be+3%2B+chars", status_code=303)
    if len(password) < 6:
        return RedirectResponse("/register?err=Password+must+be+6%2B+chars", status_code=303)
    with get_conn() as conn:
        existing = conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            return RedirectResponse("/register?err=Username+already+taken", status_code=303)
        conn.execute("INSERT INTO users (username, password) VALUES (?,?)",
                     (username, hash_password(password)))
    return RedirectResponse("/login?ok=1", status_code=303)


# ─────────────────────────────────────────────
#  AUTH — LOGIN
# ─────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, err: str = None, ok: str = None):
    user = get_user(request)
    if user:
        return RedirectResponse("/dashboard")
    notice = alert("Account created! Please log in.", "success") if ok else ""
    err_html = alert(err) if err else ""
    body = f"""
    <div class="max-w-md mx-auto">
      <div class="glass-card rounded-3xl p-8">
        <div class="flex items-center gap-3 mb-8">
          <div class="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30
                      flex items-center justify-center text-lg">🔑</div>
          <div>
            <h2 class="text-xl font-bold">Welcome Back</h2>
            <p class="text-slate-500 text-xs">Sign in to your account</p>
          </div>
        </div>
        {notice}{err_html}
        <form action="/login" method="post" class="space-y-4">
          <div>
            <label class="text-xs font-medium text-slate-400 mb-1.5 block">Username</label>
            <input name="username" placeholder="your_username" required
                   class="w-full rounded-xl px-4 py-3 text-sm">
          </div>
          <div>
            <label class="text-xs font-medium text-slate-400 mb-1.5 block">Password</label>
            <input name="password" type="password" placeholder="••••••••" required
                   class="w-full rounded-xl px-4 py-3 text-sm">
          </div>
          <button type="submit" class="btn-primary w-full py-3 rounded-xl text-sm mt-2">
            Sign In
          </button>
        </form>
        <p class="text-center text-xs text-slate-600 mt-5">
          No account?
          <a href="/register" class="text-indigo-400 hover:text-indigo-300">Register</a>
        </p>
      </div>
    </div>"""
    return layout(body, title="Login")


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, hash_password(password))
        ).fetchone()
    if not row:
        return RedirectResponse("/login?err=Invalid+credentials", status_code=303)
    request.session["user"] = username
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")


# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, msg: str = None, err: str = None):
    user = get_user(request)
    if not user:
        return RedirectResponse("/login")

    with get_conn() as conn:
        scripts = conn.execute(
            "SELECT * FROM scripts WHERE owner=? ORDER BY updated_at DESC",
            (user,)
        ).fetchall()
        total_views = conn.execute(
            "SELECT COALESCE(SUM(views),0) FROM scripts WHERE owner=?", (user,)
        ).fetchone()[0]

    notice  = alert(msg, "success") if msg else ""
    err_html = alert(err) if err else ""

    # Script cards
    if scripts:
        cards = ""
        for s in scripts:
            raw_url = f"/raw/{s['id']}"
            loadstr = f'loadstring(game:HttpGet("{{}}{raw_url}"))()'.format("")
            cards += f"""
            <div class="glass-card rounded-2xl p-5 group">
              <!-- header -->
              <div class="flex items-start justify-between gap-2 mb-3">
                <div class="min-w-0">
                  <h3 class="font-semibold truncate text-sm">{s['title']}</h3>
                  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1">
                    <span class="text-slate-600 text-xs mono">{s['id']}</span>
                    <span class="text-slate-500 text-xs">👁 {s['views']:,} views</span>
                    <span class="text-slate-600 text-xs">{s['updated_at'][:10]}</span>
                  </div>
                </div>
                <!-- delete -->
                <form action="/delete/{s['id']}" method="post" class="shrink-0"
                      onsubmit="return confirm('Delete this script?')">
                  <button class="text-slate-700 hover:text-red-400 p-1.5 rounded-lg
                                 hover:bg-red-500/10 transition-colors" title="Delete">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                  </button>
                </form>
              </div>

              <!-- loadstring box -->
              <div class="loadstring-box mb-3 text-xs"
                   onclick="copyLoadstring('{s['id']}')"
                   title="Click to copy loadstring">
                loadstring(game:HttpGet("{{}}/raw/{s['id']}"))()
              </div>

              <!-- action buttons -->
              <div class="flex flex-wrap gap-2">
                <button onclick="copyLoadstring('{s['id']}')"
                        class="flex-1 text-xs font-semibold py-2 px-3 rounded-lg
                               bg-indigo-600/15 hover:bg-indigo-600/25 text-indigo-400
                               border border-indigo-500/20 transition-colors">
                  Copy Loadstring
                </button>
                <button onclick="copyRawUrl('{s['id']}')"
                        class="flex-1 text-xs font-semibold py-2 px-3 rounded-lg
                               glass hover:bg-white/5 text-slate-300
                               transition-colors">
                  Copy Raw URL
                </button>
                <a href="/raw/{s['id']}"
                   target="_blank"
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

    # Summary bar
    summary = f"""
    <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-8">
      <div class="glass-card rounded-xl p-4 text-center">
        <div class="text-2xl font-black text-indigo-400">{len(scripts)}</div>
        <div class="text-slate-500 text-xs mt-0.5">Scripts</div>
      </div>
      <div class="glass-card rounded-xl p-4 text-center">
        <div class="text-2xl font-black text-violet-400">{total_views:,}</div>
        <div class="text-slate-500 text-xs mt-0.5">Total Views</div>
      </div>
      <div class="col-span-2 sm:col-span-1 glass-card rounded-xl p-4 text-center">
        <div class="text-2xl font-black text-emerald-400">Free</div>
        <div class="text-slate-500 text-xs mt-0.5">Plan</div>
      </div>
    </div>"""

    content = f"""
    <div class="mb-8">
      <h1 class="text-2xl sm:text-3xl font-black mb-1">
        Welcome, <span class="text-indigo-400">{user}</span> 👋
      </h1>
      <p class="text-slate-500 text-sm">Manage your Lua scripts below.</p>
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
              <textarea name="content" rows="9" required
                        placeholder="-- paste your Lua code here"
                        class="w-full rounded-xl px-3 py-2.5 text-xs mono resize-none"></textarea>
            </div>
            <button type="submit" class="btn-primary w-full py-3 rounded-xl text-sm">
              Upload to CDN ↑
            </button>
          </form>
        </div>
      </div>

      <!-- Script List -->
      <div class="lg:col-span-2">
        <h2 class="font-bold mb-4 flex items-center justify-between">
          <span>My Scripts</span>
          <span class="text-xs text-slate-600 font-normal">{len(scripts)} total</span>
        </h2>
        <div class="space-y-3">
          {cards}
        </div>
      </div>

    </div>

    <script>
      // Fix the loadstring boxes to show actual origin
      document.querySelectorAll('.loadstring-box').forEach(el => {{
        el.textContent = el.textContent.replace('{{}}', window.location.origin);
      }});
    </script>
    """
    return layout(content, user, "Dashboard")


# ─────────────────────────────────────────────
#  UPLOAD
# ─────────────────────────────────────────────
@app.post("/upload")
async def upload(request: Request, title: str = Form(...), content: str = Form(...)):
    user = get_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if not title.strip() or not content.strip():
        return RedirectResponse("/dashboard?err=Title+and+content+required", status_code=303)

    sid = gen_id(10)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO scripts (id, title, owner, updated_at) VALUES (?,?,?,?)",
            (sid, title.strip(), user, now)
        )
        conn.execute(
            "INSERT INTO versions (script_id, content, v) VALUES (?,?,1)",
            (sid, content)
        )

    return RedirectResponse(f"/dashboard?msg=Script+uploaded+successfully", status_code=303)


# ─────────────────────────────────────────────
#  RAW (serve script content)
# ─────────────────────────────────────────────
@app.get("/raw/{script_id}", response_class=PlainTextResponse)
async def raw(script_id: str):
    with get_conn() as conn:
        script = conn.execute(
            "SELECT * FROM scripts WHERE id=?", (script_id,)
        ).fetchone()
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        # get latest version
        ver = conn.execute(
            "SELECT content FROM versions WHERE script_id=? ORDER BY v DESC LIMIT 1",
            (script_id,)
        ).fetchone()
        if not ver:
            raise HTTPException(status_code=404, detail="No content found")

        # increment views
        conn.execute("UPDATE scripts SET views=views+1 WHERE id=?", (script_id,))

    return PlainTextResponse(ver["content"], media_type="text/plain; charset=utf-8")


# ─────────────────────────────────────────────
#  DELETE
# ─────────────────────────────────────────────
@app.post("/delete/{script_id}")
async def delete_script(request: Request, script_id: str):
    user = get_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    with get_conn() as conn:
        script = conn.execute(
            "SELECT owner FROM scripts WHERE id=?", (script_id,)
        ).fetchone()
        if not script or script["owner"] != user:
            return RedirectResponse("/dashboard?err=Script+not+found+or+unauthorized", status_code=303)

        conn.execute("DELETE FROM scripts WHERE id=?", (script_id,))
        conn.execute("DELETE FROM versions WHERE script_id=?", (script_id,))

    return RedirectResponse("/dashboard?msg=Script+deleted", status_code=303)


# ─────────────────────────────────────────────
#  HEALTH CHECK (Render keep-alive)
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
