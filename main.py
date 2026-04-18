import os
import random
import string
import time
from fastapi import FastAPI, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import get_db

# --- AUTOMATIC DIRECTORY FIX ---
# This prevents the "RuntimeError: Directory 'static' does not exist"
required_folders = ["static", "templates"]
for folder in required_folders:
    if not os.path.exists(folder):
        os.makedirs(folder)
        # Create a dummy file so Git/Render tracks the folder
        with open(os.path.join(folder, ".keep"), "w") as f:
            f.write("")

app = FastAPI()

# Mount static files safely
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# Simple In-Memory Rate Limiting (IP: last_upload_time)
upload_history = {}

def generate_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.post("/upload")
async def upload_script(request: Request, title: str = Form(...), content: str = Form(...)):
    client_ip = request.client.host
    current_time = time.time()
    
    # 10 second rate limit
    if client_ip in upload_history and current_time - upload_history[client_ip] < 10:
        raise HTTPException(status_code=429, detail="Please wait 10 seconds between uploads.")
    
    if not content.strip() or len(content) > 500000:
        raise HTTPException(status_code=400, detail="Script is empty or too large (Max 500KB).")

    db = get_db()
    script_id = generate_id()
    
    db.execute("INSERT INTO scripts (id, title) VALUES (?, ?)", (script_id, title))
    db.execute("INSERT INTO versions (script_id, content, version_number) VALUES (?, ?, ?)", 
               (script_id, content, 1))
    db.commit()
    
    upload_history[client_ip] = current_time
    
    base_url = str(request.base_url).rstrip('/')
    return {
        "id": script_id,
        "raw_url": f"{base_url}/raw/{script_id}",
        "version": 1
    }

@app.get("/raw/{script_id}")
async def get_raw_script(script_id: str, v: int = None):
    db = get_db()
    if v:
        row = db.execute("SELECT content FROM versions WHERE script_id = ? AND version_number = ?", 
                         (script_id, v)).fetchone()
    else:
        row = db.execute("SELECT content FROM versions WHERE script_id = ? ORDER BY version_number DESC LIMIT 1", 
                         (script_id,)).fetchone()
    
    if not row:
        return Response(content="-- Script not found or deleted", media_type="text/plain")

    # Tracking view count
    db.execute("UPDATE scripts SET views = views + 1 WHERE id = ?", (script_id,))
    db.commit()

    return Response(content=row['content'], media_type="text/plain")

@app.get("/api/scripts")
async def list_scripts():
    db = get_db()
    scripts = db.execute('''
        SELECT s.*, MAX(v.version_number) as latest_version 
        FROM scripts s 
        JOIN versions v ON s.id = v.script_id 
        GROUP BY s.id ORDER BY s.created_at DESC
    ''').fetchall()
    return [dict(row) for row in scripts]

@app.post("/delete/{script_id}")
async def delete_script(script_id: str):
    db = get_db()
    db.execute("DELETE FROM scripts WHERE id = ?", (script_id,))
    db.execute("DELETE FROM versions WHERE script_id = ?", (script_id,))
    db.commit()
    return {"status": "deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
