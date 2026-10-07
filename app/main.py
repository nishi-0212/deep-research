from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import Research, ResearchRequest
from . import store
from .pipeline import run
from pathlib import Path
from fastapi.responses import FileResponse

STATIC = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Workmate Deep Research POC")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.post("/api/research")
def start(req: ResearchRequest, bg: BackgroundTasks, x_user_id: str = Header("admin")):
    r = Research(user_id=x_user_id, question=req.question, sources=req.sources)
    store.save(r)
    bg.add_task(run, r.id)
    return {"research_id": r.id}


def _own(rid: str, user_id: str) -> Research:
    r = store.get(rid)
    if not r or r.user_id != user_id:
        raise HTTPException(404, "Not found")
    return r


@app.get("/api/research/{rid}")
def get_research(rid: str, x_user_id: str = Header("admin")):
    return _own(rid, x_user_id)


@app.get("/api/research/{rid}/progress")
def progress(rid: str, x_user_id: str = Header("admin")):
    r = _own(rid, x_user_id)
    return {"status": r.status, "steps": r.steps}


@app.get("/api/research")
def history(x_user_id: str = Header("admin")):
    return [{"id": r.id, "question": r.question, "status": r.status,
             "created_at": r.created_at} for r in store.list_for_user(x_user_id)]

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")