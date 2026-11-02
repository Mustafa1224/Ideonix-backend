import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import auth
from .config import settings
from .db import Analysis, User, check_db, get_db, init_db, recover_interrupted_jobs
from .pipeline import run_pipeline
from .ratelimit import RateLimiter
from .schemas import AnalysisOut, AnalysisStatus, AnalysisSummary, AnalyzeIn

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ideonix")
analysis_limiter = RateLimiter(settings.analyses_per_hour, 3600, "Analysis limit reached.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    init_db()
    n = recover_interrupted_jobs()
    if n:
        log.warning("Marked %d interrupted analyses as failed", n)
    log.info("Ideonix started (env=%s, ai=%s)", settings.app_env, settings.ai_providers())
    yield


app = FastAPI(title="Ideonix API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)


@app.get("/health", tags=["meta"])
def health():
    ok = check_db()
    body = {"status": "ok" if ok else "degraded", "database": "ok" if ok else "unreachable", "ai_providers": settings.ai_providers()}
    return JSONResponse(body, status_code=200 if ok else 503)


def _owned(db: Session, user: User, analysis_id: str) -> Analysis:
    row = db.get(Analysis, analysis_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Analysis not found")
    return row


@app.post("/analyses", response_model=AnalysisStatus, status_code=202, tags=["analyses"])
def create_analysis(
    body: AnalyzeIn,
    background: BackgroundTasks,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    running = db.scalar(
        select(func.count()).select_from(Analysis).where(Analysis.user_id == user.id, Analysis.status.in_(["queued", "running"]))
    )
    if running >= settings.max_running_per_user: # type: ignore
        raise HTTPException(429, "You already have analyses running. Wait for one to finish before starting another.")
    analysis_limiter.check(f"user:{user.id}")
    row = Analysis(user_id=user.id, idea_text=body.idea_text.strip(), status="queued")
    db.add(row)
    db.commit()
    background.add_task(run_pipeline, row.id)
    return AnalysisStatus(id=row.id, status=row.status) # type: ignore


@app.get("/analyses", response_model=list[AnalysisSummary], tags=["analyses"])
def list_analyses(user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Analysis).where(Analysis.user_id == user.id).order_by(Analysis.created_at.desc())).all()
    out = []
    for r in rows:
        score = (r.result or {}).get("score") or {}
        out.append(
            AnalysisSummary(
                id=r.id, idea_text=r.idea_text, status=r.status,
                verdict=score.get("verdict"), score=score.get("total"), created_at=r.created_at,
            )
        )
    return out


@app.get("/analyses/{analysis_id}", response_model=AnalysisOut, tags=["analyses"])
def get_analysis(analysis_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    r = _owned(db, user, analysis_id)
    return AnalysisOut(
        id=r.id, status=r.status, stage=r.stage, error=r.error, # type: ignore
        idea_text=r.idea_text, created_at=r.created_at, result=r.result,
    )


@app.get("/analyses/{analysis_id}/status", response_model=AnalysisStatus, tags=["analyses"])
def get_status(analysis_id: str, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    r = _owned(db, user, analysis_id)
    return AnalysisStatus(id=r.id, status=r.status, stage=r.stage, error=r.error) # type: ignore


@app.get("/stats", tags=["analyses"])
def stats(user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    """Numbers for the dashboard charts, built from the logged-in user's completed analyses."""
    rows = db.scalars(select(Analysis).where(Analysis.user_id == user.id, Analysis.status == "completed")).all()
    now = datetime.now(timezone.utc)
    months, y, m = [], now.year, now.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    trend = {k: {"ideas": 0, "approved": 0} for k in months}
    verdicts = {"Build": 0, "Pivot": 0, "Avoid": 0}
    cats = defaultdict(list)
    for r in rows:
        res = r.result or {}
        score = res.get("score") or {}
        key = (r.created_at.year, r.created_at.month)
        if key in trend:
            trend[key]["ideas"] += 1
            if score.get("verdict") == "Build":
                trend[key]["approved"] += 1
        if score.get("verdict") in verdicts:
            verdicts[score["verdict"]] += 1
        cat = (res.get("idea") or {}).get("category")
        if cat and score.get("total") is not None:
            cats[cat].append(score["total"])
    return {
        "idea_trend": [{"month": datetime(yy, mm, 1).strftime("%b"), **v} for (yy, mm), v in trend.items()],
        "category_data": sorted(
            ({"name": c, "score": round(sum(sc) / len(sc))} for c, sc in cats.items()), key=lambda x: -x["score"]
        )[:5],
        "verdict_data": [{"name": k, "value": v} for k, v in verdicts.items()],
        "total_ideas": len(rows),
    }


# ---- serve the built website (frontend/dist) from the same server; keep this block LAST ----
FRONTEND_DIR = (Path(__file__).resolve().parent.parent.parent / "frontend" / "dist").resolve()
if FRONTEND_DIR.is_dir():
    if (FRONTEND_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = (FRONTEND_DIR / path).resolve()
        if path and file.is_file() and FRONTEND_DIR in file.parents:
            return FileResponse(file)
        return FileResponse(FRONTEND_DIR / "index.html")