import os
import sqlite3
import random
import string
import time
from fastapi import FastAPI, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse

# --- DATABASE SETUP ---
def get_db():
    conn = sqlite3.connect("scripts.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

db = get_db()
db.execute("CREATE TABLE IF NOT EXISTS scripts (id TEXT PRIMARY KEY, title TEXT, views INTEGER DEFAULT 0)")
db.execute("CREATE TABLE IF NOT EXISTS versions (id INTEGER PRIMARY KEY, script_id TEXT, content TEXT, v INTEGER)")
db.commit()

app = FastAPI()
upload_history = {}

# --- UI TEMPLATES (Built-in) ---
BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ScriptCDN</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #020617; color: white; }
        .glass { background: rgba(255,255,255,0.03); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
    </style>
</head>
<body class="p-6">
    <nav class="max-w-4xl mx-auto flex justify-between mb-10">
        <b class="text-xl text-blue-400">ScriptCDN</b>
        <div class="space-x-4">
            <a href="/" class="text-sm">Upload</a>
            <a href="/dashboard" class="text-sm">My Scripts</a>
        </div>
    </nav>
    <main class="max-w-4xl mx-auto">{content}</main>
</body>
</html>
"""

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home():
    content = """
    <div class="glass p-8 rounded-2xl">
        <h2 class="text-2xl font-bold mb-4">Upload Lua Script</h2>
        <form action="/upload" method="post" class="space-y-4">
            <input type="text" name="title" placeholder="Script Name" class="w-full bg-white/5 p-3 rounded-lg outline-none border border-white/10 focus:border-blue-500">
            <textarea name="content" rows="8" placeholder="print('Hello World')" class="w-full bg-white/5 p-3 rounded-lg outline-none border border-white/10 font-mono text-sm"></textarea>
            <button type="submit" class="w-full bg-blue-600 py-3 rounded-lg font-bold">Deploy to CDN</button>
        </form>
    </div>
    """
    return BASE_HTML.format(content=content)

@app.post("/upload")
async def upload(request: Request, title: str = Form(...), content: str = Form(...)):
    sid = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    db = get_db()
    db.execute("INSERT INTO scripts (id, title) VALUES (?, ?)", (sid, title))
    db.execute("INSERT INTO versions (script_id, content, v) VALUES (?, ?, ?)", (sid, content, 1))
    db.commit()
    return HTMLResponse(f"<script>alert('Uploaded!'); window.location.href='/dashboard';</script>")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    db = get_db()
    rows = db.execute("SELECT * FROM scripts ORDER BY id DESC").fetchall()
    cards = ""
    for r in rows:
        url = f"/raw/{r['id']}"
        cards += f"""
        <div class="glass p-5 rounded-xl mb-4">
            <h3 class="font-bold">{r['title']}</h3>
            <p class="text-xs text-gray-500 mb-4">ID: {r['id']} | Views: {r['views']}</p>
            <div class="flex gap-2">
                <button onclick="navigator.clipboard.writeText('loadstring(game:HttpGet(\\''+window.location.origin+'{url}\\'))()'); alert('Copied!')" class="bg-blue-600 px-4 py-2 rounded text-xs">Copy Loadstring</button>
                <a href="{url}" target="_blank" class="bg-white/10 px-4 py-2 rounded text-xs">View Raw</a>
            </div>
        </div>
        """
    return BASE_HTML.format(content=f"<h2 class='text-xl font-bold mb-6'>My Scripts</h2>{cards if cards else '<p>No scripts yet.</p>'}")

@app.get("/raw/{sid}")
async def raw(sid: str):
    db = get_db()
    row = db.execute("SELECT content FROM versions WHERE script_id = ? ORDER BY v DESC LIMIT 1", (sid,)).fetchone()
    if not row: return Response("-- Not Found", media_type="text/plain")
    db.execute("UPDATE scripts SET views = views + 1 WHERE id = ?", (sid,))
    db.commit()
    return Response(content=row['content'], media_type="text/plain")
        
