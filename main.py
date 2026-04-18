import os
import sqlite3
import random
import string
import time
from fastapi import FastAPI, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- 1. SETUP DIRECTORIES & DATABASE ---
required_folders = ["static", "templates"]
for folder in required_folders:
    if not os.path.exists(folder):
        os.makedirs(folder)

def get_db():
    conn = sqlite3.connect("scripts.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize Database Table
db = get_db()
db.execute('''CREATE TABLE IF NOT EXISTS scripts (
    id TEXT PRIMARY KEY, title TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, views INTEGER DEFAULT 0
)''')
db.execute('''CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, script_id TEXT, content TEXT, version_number INTEGER
)''')
db.commit()

# --- 2. APP INITIALIZATION ---
app = FastAPI()

# Mount static files safely
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# --- 3. HELPER FUNCTIONS ---
upload_history = {}

def generate_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# --- 4. ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception:
        return HTMLResponse("<h1>Setup incomplete</h1><p>Please ensure templates/index.html exists.</p>")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/upload")
async def upload_script(request: Request, title: str = Form(...), content: str = Form(...)):
    client_ip = request.client.host
    current_time = time.time()
    
    if client_ip in upload_history and current_time - upload_history[client_ip] < 5:
        raise HTTPException(status_code=429, detail="Wait 5 seconds.")
    
    db = get_db()
    script_id = generate_id()
    db.execute("INSERT INTO scripts (id, title) VALUES (?, ?)", (script_id, title))
    db.execute("INSERT INTO versions (script_id, content, version_number) VALUES (?, ?, ?)", (script_id, content, 1))
    db.commit()
    
    upload_history[client_ip] = current_time
    return {"id": script_id, "raw_url": f"{request.base_url}raw/{script_id}"}

@app.get("/raw/{script_id}")
async def get_raw_script(script_id: str, v: int = None):
    db = get_db()
    if v:
        row = db.execute("SELECT content FROM versions WHERE script_id = ? AND version_number = ?", (script_id, v)).fetchone()
    else:
        row = db.execute("SELECT content FROM versions WHERE script_id = ? ORDER BY version_number DESC LIMIT 1", (script_id,)).fetchone()
    
    if not row:
        return Response(content="-- Script not found", media_type="text/plain")

    db.execute("UPDATE scripts SET views = views + 1 WHERE id = ?", (script_id,))
    db.commit()
    return Response(content=row['content'], media_type="text/plain")

@app.get("/api/scripts")
async def list_scripts():
    db = get_db()
    scripts = db.execute("SELECT s.*, MAX(v.version_number) as latest_version FROM scripts s JOIN versions v ON s.id = v.script_id GROUP BY s.id").fetchall()
    return [dict(row) for row in scripts]

@app.post("/delete/{script_id}")
async def delete_script(script_id: str):
    db = get_db()
    db.execute("DELETE FROM scripts WHERE id = ?", (script_id,))
    db.commit()
    return {"status": "ok"}
    
