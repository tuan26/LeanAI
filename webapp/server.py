"""LeanAI — web app học 90 ngày. Chạy local, không cần internet.

    python -m webapp.server          # hoặc: uvicorn webapp.server:app --reload
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import core

STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="LeanAI", docs_url="/api/docs")

# bản đồ đáp án của phiên quiz đang mở (1 người dùng, chạy local)
_answer_map: dict[str, int] = {}


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
    correct: bool | None = None     # open/recall: tự chấm


class SessionIn(BaseModel):
    label: str
    right: int
    total: int


class BudgetIn(BaseModel):
    budget_usd: float


# --------------------------------------------------------------------- API
@app.get("/api/overview")
def api_overview():
    return core.overview()


@app.get("/api/day/{day}")
def api_day(day: int):
    les = core.lessons().get(day)
    if not les:
        raise HTTPException(404, f"Không có ngày {day}")
    ov = {d["day"]: d for d in core.overview()["days"]}
    return {
        "day": day, "title": les.title, "phase": les.phase,
        "html": les.html, "sections": les.sections,
        "pass_criteria": les.pass_criteria,
        "file": str(les.path.relative_to(core.ROOT)).replace("\\", "/"),
        "prev": day - 1 if day > 1 else None,
        "next": day + 1 if day < 90 else None,
        "state": ov.get(day, {}),
        "milestone": core.MILESTONES.get(day, ""),
    }


@app.post("/api/day/{day}/status")
def api_set_status(day: int, body: StatusIn):
    if not 1 <= day <= 90:
        raise HTTPException(400, "Ngày phải trong 1..90")
    core.set_day_status(day, body.status, cost=body.cost, minutes=body.minutes,
                        note=body.note, date=body.date)
    return core.overview()


@app.get("/api/quiz")
def api_quiz(day: int | None = None, mode: str = "day", limit: int = 25):
    qs, amap = core.build_quiz(day=day, mode=mode, limit=limit)
    _answer_map.clear()
    _answer_map.update(amap)
    return {"mode": mode, "day": day, "questions": qs, "count": len(qs)}


@app.post("/api/quiz/answer")
def api_answer(body: AnswerIn):
    if body.correct is not None:
        correct = body.correct
        right_index = None
    else:
        if body.qid not in _answer_map:
            raise HTTPException(409, "Phiên quiz đã hết hạn, hãy tải lại")
        right_index = _answer_map[body.qid]
        correct = body.choice == right_index
    card = core.grade(body.qid, correct)
    return {"correct": correct, "right_index": right_index, "card": card}


@app.post("/api/quiz/session")
def api_session(body: SessionIn):
    core.record_session(body.label, body.right, body.total)
    return {"ok": True}


@app.get("/api/search")
def api_search(q: str):
    return {"q": q, "results": core.search(q)}


@app.post("/api/budget")
def api_budget(body: BudgetIn):
    st = core.load_status()
    st["budget_usd"] = body.budget_usd
    core.save_status(st)
    return core.overview()


@app.post("/api/reload")
def api_reload():
    core.reload_lessons()
    return {"ok": True, "lessons": len(core.lessons())}


# ------------------------------------------------------------------ static
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/day/{day}")
def index_day(day: int):
    return FileResponse(STATIC / "index.html")


def main() -> None:
    import socket
    import uvicorn

    port = 8080
    with socket.socket() as s:
        while port < 8100:
            try:
                s.bind(("127.0.0.1", port))
                break
            except OSError:
                port += 1
    print(f"\n  LeanAI đang chạy tại  http://127.0.0.1:{port}\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
