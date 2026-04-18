import os
import sqlite3
import random
import string
import secrets
from fastapi import FastAPI, Request, Form, HTTPException, Response, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

# --- CONFIG & DATABASE ---
DB_PATH = "azhxss.db"
SECRET_KEY = secrets.token_hex(16)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS scripts (id TEXT PRIMARY KEY, title TEXT, owner TEXT, views INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS versions (script_id TEXT, content TEXT, v INTEGER)")
    conn.commit()
    conn.close()

init_db()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# --- UI COMPONENTS (Modern Dark Theme) ---
THEME_COLOR = "#3b82f6" # Blue accent
BG_COLOR = "#020617"

def layout(content: str, user: str = None):
    auth_links = f'<a href="/dashboard" class="hover:text-blue-400">Dashboard</a> <a href="/logout" class="text-red-400">Logout</a>' if user else '<a href="/login" class="hover:text-blue-400">Login</a> <a href="/register" class="bg-blue-600 px-4 py-2 rounded-lg">Sign Up</a>'
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>azhxss script hosting</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body {{ background-color: {BG_COLOR}; color: white; font-family: 'Inter', sans-serif; }}
            .glass {{ background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.1); }}
            .neon-text {{ text-shadow: 0 0 10px {THEME_COLOR}66; }}
        </style>
    </head>
    <body class="p-4 md:p-8">
        <nav class="max-w-5xl mx-auto flex justify-between items-center mb-12">
            <a href="/" class="text-2xl font-black neon-text italic">azhxss <span class="text-blue-500">CDN</span></a>
            <div class="flex items-center gap-6 text-sm font-medium">{auth_links}</div>
        </nav>
        <main class="max-w-5xl mx-auto">{content}</main>
        <footer class="text-center mt-20 text-gray-600 text-xs">
            Contact Telegram: <a href="https://t.me/azhxss" class="text-blue-500">@azhxss</a>
        </footer>
    </body>
    </html>
    """

# --- AUTH LOGIC ---
def get_current_user(request: Request):
    return request.session.get("user")

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = get_current_user(request)
    hero = """
    <div class="text-center py-20">
        <h1 class="text-5xl md:text-7xl font-extrabold mb-6">High Performance <span class="text-blue-500">Lua</span> Hosting.</h1>
        <p class="text-gray-400 text-lg mb-10">Fast, secure, and optimized for Roblox loadstrings.</p>
        <div class="flex justify-center gap-4">
            <a href="/register" class="bg-blue-600 hover:bg-blue-700 px-8 py-4 rounded-2xl font-bold transition">Get Started</a>
            <a href="https://t.me/azhxss" class="glass px-8 py-4 rounded-2xl font-bold transition">Contact Developer</a>
        </div>
    </div>
    """
    return layout(hero, user)

@app.get("/register", response_class=HTMLResponse)
async def reg_page():
    return layout('<div class="max-w-md mx-auto glass p-8 rounded-3xl"><h2 class="text-2xl font-bold mb-6">Create Account</h2><form action="/register" method="post" class="space-y-4"><input name="username" placeholder="Username" class="w-full bg-white/5 border border-white/10 p-4 rounded-xl outline-none" required><input name="password" type="password" placeholder="Password" class="w-full bg-white/5 border border-white/10 p-4 rounded-xl outline-none" required><button class="w-full bg-blue-600 py-4 rounded-xl font-bold">Sign Up</button></form></div>')

@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT INTO users VALUES (?, ?)", (username, password))
        conn.commit()
    except:
        return "Username taken."
    finally: conn.close()
    return RedirectResponse("/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return layout('<div class="max-w-md mx-auto glass p-8 rounded-3xl"><h2 class="text-2xl font-bold mb-6">Welcome Back</h2><form action="/login" method="post" class="space-y-4"><input name="username" placeholder="Username" class="w-full bg-white/5 border border-white/10 p-4 rounded-xl outline-none" required><input name="password" type="password" placeholder="Password" class="w-full bg-white/5 border border-white/10 p-4 rounded-xl outline-none" required><button class="w-full bg-blue-600 py-4 rounded-xl font-bold">Login</button></form></div>')

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
    conn.close()
    if user:
        request.session["user"] = username
        return RedirectResponse("/dashboard", status_code=303)
    return "Invalid credentials."

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user: return RedirectResponse("/login")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    scripts = conn.execute("SELECT * FROM scripts WHERE owner = ?", (user,)).fetchall()
    conn.close()
    
    script_list = "".join([f'<div class="glass p-6 rounded-2xl mb-4 flex justify-between items-center"><div><h3 class="font-bold">{s["title"]}</h3><p class="text-xs text-gray-500">ID: {s["id"]} | Views: {s["views"]}</p></div><div class="flex gap-2"><button onclick="copyLink(\'{s["id"]}\')" class="bg-blue-600/20 text-blue-400 px-4 py-2 rounded-lg text-xs font-bold">Copy Loadstring</button><a href="/raw/{s["id"]}" class="bg-white/5 px-4 py-2 rounded-lg text-xs">Raw</a></div></div>' for s in scripts])
    
    content = f"""
    <div class="grid md:grid-cols-3 gap-8">
        <div class="md:col-span-1 glass p-6 rounded-3xl h-fit">
            <h2 class="text-xl font-bold mb-4">Upload Script</h2>
            <form action="/upload" method="post" class="space-y-4">
                <input name="title" placeholder="Script Name" class="w-full bg-white/5 border border-white/10 p-3 rounded-xl outline-none text-sm" required>
                <textarea name="content" rows="6" placeholder="-- Your Lua Code here" class="w-full bg-white/5 border border-white/10 p-3 rounded-xl outline-none font-mono text-xs" required></textarea>
                <button class="w-full bg-blue-600 py-3 rounded-xl font-bold text-sm">Upload to CDN</button>
            </form>
        </div>
        <div class="md:col-span-2">
            <h2 class="text-xl font-bold mb-4">My Scripts</h2>
            {script_list if script_list else '<p class="text-gray-600">No scripts yet.</p>'}
        </div>
    </div>
    <script>
    function copyLink(id) {{
        const url = window.location.origin + '/raw/' + id;
        const code = `loadstring(game:HttpGet("${{url}}"))()`;
        navigator.clipboard.writeText(code);
        alert('Loadstring copied!');
    }}
    </script>
    """
    return layout(content, user)

@app.post("/upload")
async def upload(request: Request, title: str = Form(...), content: str = Form(...)):
    user = get_current_user(request)
    if not user: return "Unauthorized"
    
    sid = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO scripts (id, title, owner) VALUES (?, ?, ?)", (sid, title, user))
    conn.execute("INSERT INTO versions VALUES (?, ?, ?)", (sid, content, 1))
    conn.commit()
    conn.close()
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/raw/{sid}")
async def raw(sid: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT content FROM versions WHERE script_id = ? ORDER BY v DESC LIMIT 1", (sid,)).fetchone()
    if not row: return Response("-- Script Not Found", media_type="text/plain")
    conn.execute("UPDATE scripts SET views = views + 1 WHERE id = ?", (sid,))
    conn.commit()
    conn.close()
    return Response(content=row[0], media_type="text/plain")
