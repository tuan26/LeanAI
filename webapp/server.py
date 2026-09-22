"""LeanAI — web app học 90 ngày. Chạy local, không cần internet.

    python -m webapp.server          # hoặc: uvicorn webapp.server:app --reload
"""
from __future__ import annotations

from pathlib import Path

import secrets

from fastapi import Depends, FastAPI, HTTPException, Request, status as http
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, core

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="LeanAI", docs_url="/api/docs")

# ----------------------------------------------------------------- an ninh
_basic = HTTPBasic(auto_error=False)


def require_auth(creds: HTTPBasicCredentials | None = Depends(_basic)) -> str:
    """Bật khi có LEANAI_USER + LEANAI_PASS. So sánh chống tấn công thời gian."""
    if not config.AUTH_ENABLED:
        return ""
    ok = creds is not None and (
        secrets.compare_digest(creds.username, config.USER)
        & secrets.compare_digest(creds.password, config.PASS))
    if not ok:
        raise HTTPException(http.HTTP_401_UNAUTHORIZED, "Sai tài khoản hoặc mật khẩu",
                            headers={"WWW-Authenticate": "Basic"})
    return creds.username


@app.middleware("http")
async def block_writes_when_readonly(request: Request, call_next):
    if config.READ_ONLY and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            {"detail": "Chế độ CHỈ ĐỌC — đặt LEANAI_USER/LEANAI_PASS để bật ghi."},
            status_code=http.HTTP_403_FORBIDDEN)
    return await call_next(request)

# ------------------------------------------------------------------ schemas
class StatusIn(BaseModel):
    status: str = Field(pattern="^(pass|fail|clear)$")
    cost: float = 0.0
    minutes: int = 0
    note: str = ""
    date: str = ""


class AnswerIn(BaseModel):
    qid: str
    choice: int | None = None       # mcq: vị trí đã chọn
    seed: str = ""                  # mcq: seed của phiên, để suy lại đáp án
    correct: bool | None = None     # open/recall: tự chấm


class SessionIn(BaseModel):
    label: str
    right: int
    total: int


class BudgetIn(BaseModel):
    budget_usd: float


# --------------------------------------------------------------------- API
@app.get("/api/overview")
def api_overview(_: str = Depends(require_auth)):
    return core.overview()


@app.get("/api/day/{day}")
def api_day(day: int, _: str = Depends(require_auth)):
    les = core.lesson(day)
    if not les:
        raise HTTPException(404, f"Không có ngày {day}")
    return {
        "day": day, "title": les.title, "phase": les.phase,
        "html": les.html, "sections": les.sections,
        "pass_criteria": les.pass_criteria,
        "file": str(les.path.relative_to(core.ROOT)).replace("\\", "/"),
        "prev": day - 1 if day > 1 else None,
        "next": day + 1 if day < 90 else None,
        "state": core.day_state(day),
        "milestone": core.MILESTONES.get(day, ""),
    }


@app.post("/api/day/{day}/status")
def api_set_status(day: int, body: StatusIn, _: str = Depends(require_auth)):
    if not 1 <= day <= 90:
        raise HTTPException(400, "Ngày phải trong 1..90")
    core.set_day_status(day, body.status, cost=body.cost, minutes=body.minutes,
                        note=body.note, date=body.date)
    return core.overview()


@app.get("/api/quiz")
def api_quiz(day: int | None = None, mode: str = "day", limit: int = 25,
              _: str = Depends(require_auth)):
    qs, seed = core.build_quiz(day=day, mode=mode, limit=limit)
    return {"mode": mode, "day": day, "questions": qs, "count": len(qs), "seed": seed}


@app.post("/api/quiz/answer")
def api_answer(body: AnswerIn, _: str = Depends(require_auth)):
    if body.correct is not None:
        correct = body.correct
        right_index = None
    else:
        right_index = core.correct_index(body.qid, body.seed)
        if right_index is None:
            raise HTTPException(400, f"Không chấm được câu {body.qid}")
        correct = body.choice == right_index
    card = core.grade(body.qid, correct)
    return {"correct": correct, "right_index": right_index, "card": card}


@app.post("/api/quiz/session")
def api_session(body: SessionIn, _: str = Depends(require_auth)):
    core.record_session(body.label, body.right, body.total)
    return {"ok": True}


@app.get("/api/search")
def api_search(q: str, _: str = Depends(require_auth)):
    return {"q": q, "results": core.search(q)}


@app.post("/api/budget")
def api_budget(body: BudgetIn, _: str = Depends(require_auth)):
    st = core.load_status()
    st["budget_usd"] = body.budget_usd
    core.save_status(st)
    return core.overview()


@app.post("/api/reload")
def api_reload():
    core.reload_lessons()
    return {"ok": True, "lessons": len(core.lessons())}


@app.get("/api/export")
def api_export(_: str = Depends(require_auth)):
    """Tải toàn bộ tiến trình về để sao lưu. Dùng khi dữ liệu nằm trên cloud."""
    from datetime import datetime, timezone
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
        "quiz_progress": core.load_quiz_progress(),
        "status": core.load_status(),
    }


@app.post("/api/import")
def api_import(payload: dict, _: str = Depends(require_auth)):
    """Khôi phục từ bản sao lưu. GHI ĐÈ toàn bộ tiến trình hiện tại."""
    if payload.get("version") != 1:
        raise HTTPException(400, "Không nhận ra định dạng bản sao lưu")
    qp, st = payload.get("quiz_progress"), payload.get("status")
    if not isinstance(qp, dict) or not isinstance(st, dict):
        raise HTTPException(400, "Bản sao lưu thiếu quiz_progress hoặc status")
    if "cards" not in qp or "days" not in st:
        raise HTTPException(400, "Bản sao lưu sai cấu trúc")
    core.save_quiz_progress(qp)
    core.save_status(st)
    return {"ok": True, "cards": len(qp["cards"]), "days": len(st["days"])}


@app.get("/api/diag")
def api_diag():
    """Chẩn đoán cấu hình. CHỈ báo tên biến có/không, TUYỆT ĐỐI không lộ giá trị."""
    import os
    expected = ["LEANAI_USER", "LEANAI_PASS", "LEANAI_SECRET",
                "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"]
    seen = {k: bool(os.getenv(k, "").strip()) for k in expected}
    # Bắt lỗi gõ sai tên: liệt kê MỌI biến bắt đầu bằng LEANAI/UPSTASH
    similar = sorted(k for k in os.environ
                     if k.upper().startswith(("LEANAI", "LEAN_AI", "UPSTASH")))
    missing = [k for k, v in seen.items() if not v]
    hints = []
    if missing:
        hints.append(f"Thiếu: {', '.join(missing)}")
        typo = [k for k in similar if k not in expected]
        if typo:
            hints.append(f"Tên lạ (gõ sai?): {', '.join(typo)}")
        hints.append("Kiểm tra Vercel → Settings → Environment Variables, "
                     "nhớ tick ô Production, rồi Redeploy.")
    return {
        "env_seen": seen,
        "env_names_found": similar,
        "vercel_env": os.getenv("VERCEL_ENV", ""),
        "auth_enabled": config.AUTH_ENABLED,
        "read_only": config.READ_ONLY,
        "storage": __import__("webapp.storage", fromlist=["store"]).store.name,
        "hints": hints,
    }


@app.get("/healthz")
def healthz():
    from .storage import store
    return {"ok": True, "lessons": len(core.titles()),
            "questions": len(core.all_questions()),
            "read_only": config.READ_ONLY, "auth": config.AUTH_ENABLED,
            "serverless": config.SERVERLESS, "storage": store.name,
            "writable": not config.READ_ONLY}


# ------------------------------------------------------------------ static
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index(_: str = Depends(require_auth)):
    return FileResponse(STATIC / "index.html")


@app.get("/day/{day}")
def index_day(day: int, _: str = Depends(require_auth)):
    return FileResponse(STATIC / "index.html")


def main() -> None:
    import uvicorn

    if config.DATA_DIR:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("\n" + config.banner() + "\n")
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="warning")


if __name__ == "__main__":
    main()
