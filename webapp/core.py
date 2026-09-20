"""Lõi dữ liệu cho web app — dùng CHUNG file dữ liệu với quiz/quiz.py và track.py."""
from __future__ import annotations

import datetime as dt
import json
import random
import re
import secrets
import subprocess
from dataclasses import dataclass
from pathlib import Path

import markdown

from . import config
from .storage import store

ROOT = Path(__file__).resolve().parent.parent
CURRICULUM = ROOT / "curriculum"
BANK = ROOT / "quiz" / "bank"
QUIZ_PROGRESS = config.QUIZ_PROGRESS      # đổi được bằng LEANAI_DATA_DIR
STATUS = config.STATUS_FILE

# Phải khớp tuyệt đối với quiz/quiz.py
INTERVALS = {1: 0, 2: 1, 3: 2, 4: 4, 5: 8, 6: 16}
MAX_BOX = 6

PHASES = [
    (1, "AI Fundamentals", 1, 14),
    (2, "LLM Engineering", 15, 30),
    (3, "RAG", 31, 50),
    (4, "AI Agent", 51, 65),
    (5, "AI Engineering", 66, 75),
    (6, "AI SaaS · Capstone", 76, 90),
]

MILESTONES = {
    14: "AI Explanation Engine", 21: "CLI Chatbot", 30: "AI Business Analyst",
    37: "Mini RAG", 44: "Ingestion Pipeline", 50: "Company Knowledge AI",
    65: "Research Agent", 90: "CareDesk-AI · DEMO DAY",
}

MAX_DEBT = 2


def today() -> str:
    return dt.date.today().isoformat()


def phase_of(day: int) -> int:
    for num, _, lo, hi in PHASES:
        if lo <= day <= hi:
            return num
    return 0


# ----------------------------------------------------------------- nội dung
_md = markdown.Markdown(
    extensions=["tables", "fenced_code", "codehilite", "toc", "attr_list", "sane_lists"],
    extension_configs={"codehilite": {"css_class": "hl", "guess_lang": False}},
)


@dataclass
class Lesson:
    day: int
    title: str
    phase: int
    path: Path
    raw: str

    @property
    def html(self) -> str:
        _md.reset()
        body = re.sub(r"^#\s*NGÀY.*?\n", "", self.raw, count=1)
        return _md.convert(body)

    @property
    def sections(self) -> list[dict]:
        out = []
        for m in re.finditer(r"^##\s+(.+)$", self.raw, re.M):
            t = m.group(1).strip()
            out.append({"title": t, "anchor": slug(t)})
        return out

    @property
    def pass_criteria(self) -> list[str]:
        block = re.search(r"##\s*\d*\.?\s*(?:Tiêu chí\s*)?PASS/FAIL(.*?)(?=\n##|\Z)",
                          self.raw, re.S | re.I)
        if not block:
            return []
        return [m.group(1).strip()
                for m in re.finditer(r"^-\s*\[\s*\]\s*(.+)$", block.group(1), re.M)]


def slug(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s.lower())
    return re.sub(r"[\s_]+", "-", s).strip("-")


_lessons: dict[int, Lesson] | None = None


def lessons() -> dict[int, Lesson]:
    global _lessons
    if _lessons is None:
        _lessons = {}
        for f in sorted(CURRICULUM.glob("phase*/day*.md")):
            n = int(f.stem[3:])
            raw = f.read_text(encoding="utf-8", errors="replace")
            first = raw.splitlines()[0].strip()
            m = re.match(r"#\s*NGÀY\s*\d+\s*[—-]\s*(.+)", first)
            _lessons[n] = Lesson(n, m.group(1).strip() if m else f.stem,
                                 phase_of(n), f, raw)
    return _lessons


def reload_lessons() -> None:
    global _lessons
    _lessons = None


def search(q: str, limit: int = 40) -> list[dict]:
    q = q.strip().lower()
    if len(q) < 2:
        return []
    out = []
    for n, les in sorted(lessons().items()):
        low = les.raw.lower()
        if q not in low and q not in les.title.lower():
            continue
        idx = low.find(q)
        snippet = ""
        if idx >= 0:
            s = max(0, idx - 60)
            snippet = re.sub(r"\s+", " ", les.raw[s:idx + 120]).strip()
        out.append({"day": n, "title": les.title, "phase": les.phase,
                    "snippet": snippet, "hits": low.count(q)})
        if len(out) >= limit:
            break
    return out


# -------------------------------------------------------------------- quiz
def load_quiz_progress() -> dict:
    return store.load("quiz_progress", {"cards": {}, "sessions": []})


def save_quiz_progress(p: dict) -> None:
    store.save("quiz_progress", p)


_bank_cache: dict[int, dict] | None = None


def bank() -> dict[int, dict]:
    global _bank_cache
    if _bank_cache is None:
        _bank_cache = {}
        for f in sorted(BANK.glob("day*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            _bank_cache[int(f.stem[3:])] = d
    return _bank_cache


def all_questions() -> dict[str, dict]:
    out = {}
    for day, d in bank().items():
        for q in d["questions"]:
            out[q["id"]] = {**q, "day": day, "topic": d.get("title", "")}
    return out


def card_of(prog: dict, qid: str) -> dict:
    return prog["cards"].setdefault(
        qid, {"box": 1, "due": today(), "seen": 0, "wrong": 0, "streak": 0})


def schedule(card: dict, correct: bool) -> None:
    card["seen"] += 1
    if correct:
        card["streak"] += 1
        card["box"] = min(card["box"] + 1, MAX_BOX)
    else:
        card["wrong"] += 1
        card["streak"] = 0
        card["box"] = 1
    card["due"] = (dt.date.today()
                   + dt.timedelta(days=INTERVALS[card["box"]])).isoformat()
    card["last"] = today()


def shuffle_order(qid: str, seed: str, n: int) -> list[int]:
    """Thứ tự xáo đáp án, suy lại được từ (qid, seed) nên server không cần nhớ gì.

    Client nhận seed nhưng KHÔNG biết đáp án gốc, nên không suy ngược được."""
    rnd = random.Random(f"{config.SECRET}:{qid}:{seed}")
    idx = list(range(n))
    rnd.shuffle(idx)
    return idx


def correct_index(qid: str, seed: str) -> int | None:
    """Vị trí đáp án đúng SAU KHI xáo — tính lại lúc chấm."""
    q = all_questions().get(qid)
    if not q or q.get("type") != "mcq":
        return None
    order = shuffle_order(qid, seed, len(q["choices"]))
    return order.index(q["answer"])


def build_quiz(day: int | None = None, mode: str = "day",
               limit: int = 25, seed: str = "") -> tuple[list[dict], str]:
    """Trả về (câu hỏi đã che đáp án, seed dùng để xáo)."""
    prog = load_quiz_progress()
    qs = list(all_questions().values())

    if mode == "day" and day:
        qs = [q for q in qs if q["day"] == day]
    elif mode == "review":
        qs = [q for q in qs
              if q["id"] in prog["cards"]
              and prog["cards"][q["id"]]["due"] <= today()
              and prog["cards"][q["id"]]["seen"] > 0]
        qs.sort(key=lambda q: (prog["cards"][q["id"]]["box"],
                               prog["cards"][q["id"]]["due"]))
        qs = qs[:limit]
    elif mode == "weak":
        qs = [q for q in qs
              if prog["cards"].get(q["id"], {}).get("wrong", 0) > 0]
        qs.sort(key=lambda q: -prog["cards"][q["id"]]["wrong"])
        qs = qs[:limit]

    seed = seed or secrets.token_urlsafe(9)
    random.shuffle(qs)
    out = []
    for q in qs:
        item = {"id": q["id"], "day": q["day"], "topic": q.get("topic", ""),
                "type": q.get("type", "mcq"), "q": q["q"],
                "explain": q.get("explain", ""), "keywords": q.get("keywords", [])}
        if item["type"] == "mcq":
            order = shuffle_order(q["id"], seed, len(q["choices"]))
            item["choices"] = [q["choices"][i] for i in order]
        else:
            item["answer"] = q["answer"]
        card = prog["cards"].get(q["id"])
        item["box"] = card["box"] if card else 0
        out.append(item)
    return out, seed


def grade(qid: str, correct: bool) -> dict:
    prog = load_quiz_progress()
    card = card_of(prog, qid)
    schedule(card, correct)
    save_quiz_progress(prog)
    return {"box": card["box"], "due": card["due"], "seen": card["seen"],
            "wrong": card["wrong"]}


def record_session(label: str, right: int, total: int) -> None:
    prog = load_quiz_progress()
    prog.setdefault("sessions", []).append(
        {"date": today(), "label": label, "right": right, "total": total})
    save_quiz_progress(prog)


def quiz_stats() -> dict:
    prog = load_quiz_progress()
    cards = prog.get("cards", {})
    total = len(all_questions())
    by_day: dict[int, dict] = {}
    for qid, c in cards.items():
        m = re.match(r"d(\d+)q", qid)
        if not m:
            continue
        d = by_day.setdefault(int(m.group(1)), {"seen": 0, "mastered": 0, "due": 0})
        d["seen"] += 1
        d["mastered"] += c.get("box", 1) >= 5
        d["due"] += c.get("due", today()) <= today()
    return {
        "total": total,
        "seen": len(cards),
        "mastered": sum(1 for c in cards.values() if c.get("box", 1) >= 5),
        "due": sum(1 for c in cards.values() if c.get("due", today()) <= today()),
        "by_day": by_day,
        "sessions": prog.get("sessions", []),
        "boxes": {b: sum(1 for c in cards.values() if c.get("box", 1) == b)
                  for b in range(1, MAX_BOX + 1)},
    }


# ---------------------------------------------------------------- tiến trình
def load_status() -> dict:
    return store.load("status", {"days": {}, "budget_usd": 40.0, "started": ""})


def save_status(s: dict) -> None:
    store.save("status", s)


def set_day_status(day: int, status: str, *, cost: float = 0.0,
                   minutes: int = 0, note: str = "", date: str = "") -> dict:
    st = load_status()
    if status == "clear":
        st.setdefault("days", {}).pop(str(day), None)
    else:
        st.setdefault("days", {})[str(day)] = {
            "status": status, "date": date or today(),
            "cost": cost, "minutes": minutes, "note": note}
        if not st.get("started"):
            st["started"] = today()
    save_status(st)
    return st


def git_commits() -> int:
    try:
        r = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT,
                           capture_output=True, text=True, timeout=10)
        return int(r.stdout.strip()) if r.returncode == 0 else 0
    except Exception:
        return 0


def overview() -> dict:
    st = load_status()
    qz = quiz_stats()
    les = lessons()
    days_st = {int(k): v for k, v in st.get("days", {}).items()}
    passed = sorted(d for d, v in days_st.items() if v.get("status") == "pass")
    failed = sorted(d for d, v in days_st.items() if v.get("status") == "fail")
    furthest = max(passed + failed, default=0)
    debt = [d for d in range(1, furthest + 1) if d not in passed]
    next_day = next((d for d in range(1, 91) if d not in passed), None)
    if debt and len(debt) > MAX_DEBT:
        next_day = debt[0]

    dates = sorted({v["date"] for v in days_st.values() if v.get("date")})
    streak = 0
    if dates:
        cur = dt.date.fromisoformat(dates[-1])
        if (dt.date.today() - cur).days <= 1:
            streak = 1
            for prev in reversed(dates[:-1]):
                p = dt.date.fromisoformat(prev)
                gap = (cur - p).days
                if gap == 1:
                    streak += 1; cur = p
                elif gap == 0:
                    continue
                else:
                    break

    day_list = []
    for n in range(1, 91):
        v = days_st.get(n, {})
        qd = qz["by_day"].get(n, {})
        day_list.append({
            "day": n, "title": les[n].title if n in les else f"Ngày {n}",
            "phase": phase_of(n),
            "status": v.get("status", ""),
            "date": v.get("date", ""), "note": v.get("note", ""),
            "cost": v.get("cost", 0), "minutes": v.get("minutes", 0),
            "quiz_total": len(bank().get(n, {}).get("questions", [])),
            "quiz_seen": qd.get("seen", 0), "quiz_mastered": qd.get("mastered", 0),
            "quiz_due": qd.get("due", 0),
            "milestone": MILESTONES.get(n, ""),
            "is_next": n == next_day,
        })

    phases = []
    for num, name, lo, hi in PHASES:
        done = sum(1 for d in passed if lo <= d <= hi)
        phases.append({"num": num, "name": name, "lo": lo, "hi": hi,
                       "total": hi - lo + 1, "done": done,
                       "pct": round(done / (hi - lo + 1), 4)})

    return {
        "days": day_list, "phases": phases,
        "passed": len(passed), "failed": failed, "debt": debt,
        "max_debt": MAX_DEBT, "next_day": next_day, "streak": streak,
        "cost": round(sum(float(v.get("cost", 0) or 0) for v in days_st.values()), 4),
        "budget": float(st.get("budget_usd", 40.0)),
        "minutes": sum(int(v.get("minutes", 0) or 0) for v in days_st.values()),
        "commits": git_commits(),
        "quiz": {k: qz[k] for k in ("total", "seen", "mastered", "due", "boxes")},
        "milestones": [{"day": d, "name": n, "done": d in passed}
                       for d, n in MILESTONES.items()],
        "started": st.get("started", ""),
    }
