from fastapi import FastAPI, Request, Form, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import uuid, os

from models import Base, Task, SessionLocal, engine
import config

app = FastAPI(title="Arena Agent Task Gateway", version="1.0.0")

if not os.path.exists("static"):
    os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- WEB UI ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "tron_wallet": config.TRON_WALLET,
        "evm_wallet": config.EVM_WALLET
    })

@app.post("/task/create")
async def create_task_form(
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(...),
    price_usdt: float = Form(5.0),
    payment_rail: str = Form("TRC20"),
    client_contact: str = Form(None),
    db: Session = Depends(get_db)
):
    task_id = str(uuid.uuid4())
    task = Task(
        id=task_id,
        title=title,
        category=category,
        description=description,
        price_usdt=price_usdt,
        payment_rail=payment_rail,
        client_contact=client_contact
    )
    db.add(task)
    db.commit()
    return RedirectResponse(url=f"/task/{task_id}", status_code=303)

@app.get("/task/{task_id}", response_class=HTMLResponse)
async def task_status_page(request: Request, task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    wallet = config.TRON_WALLET if task.payment_rail == "TRC20" else config.EVM_WALLET
    return templates.TemplateResponse("task_status.html", {
        "request": request,
        "task": task,
        "pay_wallet": wallet,
        "tron_wallet": config.TRON_WALLET,
        "evm_wallet": config.EVM_WALLET
    })

@app.post("/api/task/{task_id}/submit-tx")
async def submit_tx(task_id: str, tx_hash: str = Form(...), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.tx_hash = tx_hash.strip()
    task.status = "paid_queued"
    task.progress_log += f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] Клиент предоставил TXID: {task.tx_hash[:16]}... Задача добавлена в очередь агента."
    db.commit()
    return RedirectResponse(url=f"/task/{task_id}", status_code=303)

# --- AGENT WORKER API (SECURE) ---

@app.get("/api/agent/queue")
async def get_agent_queue(x_agent_secret: str = Header(None), db: Session = Depends(get_db)):
    if x_agent_secret != config.AGENT_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid Agent Secret Key")
    tasks = db.query(Task).filter(Task.status == "paid_queued").all()
    return {"tasks": [{"id": t.id, "title": t.title, "category": t.category, "description": t.description, "price_usdt": t.price_usdt} for t in tasks]}

@app.post("/api/agent/task/{task_id}/start")
async def agent_start_task(task_id: str, x_agent_secret: str = Header(None), db: Session = Depends(get_db)):
    if x_agent_secret != config.AGENT_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid Agent Secret Key")
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "in_progress"
    task.progress_log += f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] Агент взял задачу в работу (sandbox init)."
    db.commit()
    return {"status": "ok"}

@app.post("/api/agent/task/{task_id}/log")
async def agent_log(task_id: str, message: str = Form(...), x_agent_secret: str = Header(None), db: Session = Depends(get_db)):
    if x_agent_secret != config.AGENT_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid Agent Secret Key")
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.progress_log += f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] {message}"
    db.commit()
    return {"status": "ok"}

@app.post("/api/agent/task/{task_id}/complete")
async def agent_complete(task_id: str, result_text: str = Form(...), result_file_url: str = Form(None), x_agent_secret: str = Header(None), db: Session = Depends(get_db)):
    if x_agent_secret != config.AGENT_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid Agent Secret Key")
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "completed"
    task.result_text = result_text
    task.result_file_url = result_file_url
    task.completed_at = datetime.utcnow()
    task.progress_log += f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] Задача успешно завершена. Артефакты готовы к загрузке."
    db.commit()
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
