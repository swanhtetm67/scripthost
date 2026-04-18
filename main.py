import os
import sqlite3
import random
import string
from fastapi import FastAPI, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse

# --- DATABASE SETUP ---
DB_PATH = "scripts.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS scripts (id TEXT PRIMARY KEY, title TEXT, views INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS versions (id INTEGER PRIMARY KEY, script_id TEXT, content TEXT, v INTEGER)")
    conn.commit()
    conn.close()

init_db()

app = FastAPI()

# --- THE UI (Safer Replacement) ---
BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ScriptCDN</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #020617; color: white; font-family: sans-serif; }
        .glass { background: rgba(255,255,255,0.03); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
    </style>
</head>
<body class="p-6">
    <nav class="max-w-4xl mx-auto flex justify-between items-center mb-10">
        <b class="text-2xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">ScriptCDN</b>
        <div class="space-x-6">
            <a href="/" class="text-sm hover:text-blue-400 transition">Upload</a>
            <a href="/dashboard" class="text-sm hover:text-blue-400 transition">Dashboard</a>
        </div>
    </nav>
    <main class="max-w-4xl mx-auto">
        REPLACE_THIS_WITH_CONTENT
    </main>
</body>
</html>
"""

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home():
    form_html = """
    <div class="glass p-8 rounded-2xl shadow-2xl">
        <h2 class="text-2xl font-bold mb-6">Upload New Script</h2>
        <form action="/upload" method="post" class="space-y-4">
            <div>
                <label class="block text-xs uppercase tracking-widest text-gray-500 mb-2">Script Title</label>
                <input type="text" name="title" required placeholder="My Roblox Script" class="w-full bg-white/5 p-4 rounded-xl outline-none border border-white/10 focus:border-blue-500 transition">
            </div>
            <div>
                <label class="block text-xs uppercase tracking-widest text-gray-500 mb-2">Lua Code</label>
                <textarea name="content" required rows="10" placeholder="print('Hello World')" class="w-full bg-white/5 p-4 rounded-xl outline-none border border-white/10 focus:border-blue-500 transition font-mono text-sm"></textarea>
            </div>
            <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 py-4 rounded-xl font-bold transition transform active:scale-95">Deploy to CDN</button>
        </form>
    </div>
    """
    return BASE_HTML.replace("REPLACE_THIS_WITH_CONTENT", form_html)

@app.post("/upload")
async def upload(title: str = Form(...), content: str = Form(...)):
    sid = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO scripts (id, title) VALUES (?, ?)", (sid, title))
    cursor.execute("INSERT INTO versions (script_id, content, v) VALUES (?, ?, ?)", (sid, content, 1))
    conn.commit()
    conn.close()
    return HTMLResponse(f"<script>alert('Script Deployed!'); window.location.href='/dashboard';</script>")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM scripts ORDER BY rowid DESC").fetchall()
    conn.close()
    
    cards = ""
    for r in rows:
        cards += f"""
        <div class="glass p-6 rounded-2xl mb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
                <h3 class="font-bold text-lg">{r['title']}</h3>
                <p class="text-xs text-gray-500">ID: {r['id']} • {r['views']} Views</p>
            </div>
            <div class="flex gap-2 w-full md:w-auto">
                <button onclick="copyLink('{r['id']}')" class="flex-1 bg-blue-600/20 text-blue-400 px-4 py-2 rounded-lg text-xs font-bold hover:bg-blue-600 hover:text-white transition">Copy Loadstring</button>
                <a href="/raw/{r['id']}" target="_blank" class="flex-1 bg-white/5 px-4 py-2 rounded-lg text-xs text-center hover:bg-white/10 transition">Raw</a>
            </div>
        </div>
        """
    
    js = """
    <script>
    function copyLink(id) {
        const url = window.location.origin + '/raw/' + id;
        const code = `loadstring(game:HttpGet("${url}"))()`;
        navigator.clipboard.writeText(code);
        alert('Loadstring copied!');
    }
    </script>
    """
    
    empty_msg = "<p class='text-center text-gray-500 py-10'>No scripts found. Upload one!</p>"
    return BASE_HTML.replace("REPLACE_THIS_WITH_CONTENT", f"<h2 class='text-2xl font-bold mb-8'>Your CDN Dashboard</h2>{cards if cards else empty_msg}{js}")

@app.get("/raw/{sid}")
async def raw(sid: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT content FROM versions WHERE script_id = ? ORDER BY v DESC LIMIT 1", (sid,)).fetchone()
    if not row:
        conn.close()
        return Response("-- Script Not Found", media_type="text/plain")
    
    conn.execute("UPDATE scripts SET views = views + 1 WHERE id = ?", (sid,))
    conn.commit()
    conn.close()
    return Response(content=row[0], media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
