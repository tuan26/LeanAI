#!/usr/bin/env python
"""LeanAI quiz engine - spaced repetition (Leitner 5 hop).

Cach dung:
    python quiz/quiz.py --day 1        # hoc quiz ngay 1
    python quiz/quiz.py --review       # on tat ca cau den han
    python quiz/quiz.py --exam 1 14    # thi tong ket phase
    python quiz/quiz.py --stats        # thong ke tri nho
    python quiz/quiz.py --weak         # 10 cau yeu nhat
    python quiz/quiz.py --doctor       # kiem tra moi truong
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BANK = ROOT / "bank"
PROGRESS = ROOT / "progress.json"

# Console Windows thuong khong phai UTF-8 -> ep lai, neu khong tieng Viet se crash
for _stream in (sys.stdout, sys.stderr, sys.stdin):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Leitner: box -> so ngay cho den lan on tiep theo
INTERVALS = {1: 0, 2: 1, 3: 2, 4: 4, 5: 8, 6: 16}
MAX_BOX = 6


# ---------------------------------------------------------------- io helpers
def today() -> str:
    return dt.date.today().isoformat()


def load_progress() -> dict:
    if PROGRESS.exists():
        try:
            return json.loads(PROGRESS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("! progress.json hong, tao moi")
    return {"cards": {}, "sessions": []}


def save_progress(p: dict) -> None:
    PROGRESS.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


def load_bank(day: int) -> dict | None:
    f = BANK / f"day{day:02d}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def all_days() -> list[int]:
    return sorted(int(f.stem[3:]) for f in BANK.glob("day*.json"))


def questions_for(days: list[int]) -> list[dict]:
    out = []
    for d in days:
        bank = load_bank(d)
        if not bank:
            continue
        for q in bank["questions"]:
            q = dict(q)
            q["day"] = d
            q["topic"] = bank.get("title", "")
            out.append(q)
    return out


# ------------------------------------------------------------------- display
class C:
    G = "\033[92m"
    R = "\033[91m"
    Y = "\033[93m"
    B = "\033[94m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    X = "\033[0m"


if os.name == "nt" and not os.environ.get("WT_SESSION"):
    try:
        import colorama  # type: ignore

        colorama.just_fix_windows_console()
    except Exception:
        pass


def rule(title: str = "") -> None:
    print(f"\n{C.DIM}{'-' * 68}{C.X}")
    if title:
        print(f"{C.BOLD}{title}{C.X}")


def ask_line(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\nDung giua chung. Tien do da luu.")
        sys.exit(0)


# ----------------------------------------------------------------- scheduling
def card_of(prog: dict, qid: str) -> dict:
    return prog["cards"].setdefault(
        qid, {"box": 1, "due": today(), "seen": 0, "wrong": 0, "streak": 0}
    )


def is_due(card: dict) -> bool:
    return card["due"] <= today()


def schedule(card: dict, correct: bool) -> None:
    card["seen"] += 1
    if correct:
        card["streak"] += 1
        card["box"] = min(card["box"] + 1, MAX_BOX)
    else:
        card["wrong"] += 1
        card["streak"] = 0
        card["box"] = 1
    days = INTERVALS[card["box"]]
    card["due"] = (dt.date.today() + dt.timedelta(days=days)).isoformat()
    card["last"] = today()


# --------------------------------------------------------------------- asking
def ask_mcq(q: dict) -> bool:
    idx = list(range(len(q["choices"])))
    random.shuffle(idx)
    for i, j in enumerate(idx):
        print(f"  {chr(65 + i)}. {q['choices'][j]}")
    ans = ask_line("\n  Tra loi (A/B/C/D, 's' = bo qua): ").upper()
    if ans == "S":
        return False
    if not ans or ans[0] not in "ABCDEF"[: len(idx)]:
        print(f"  {C.R}Khong hop le -> tinh la sai{C.X}")
        return False
    picked = idx[ord(ans[0]) - 65]
    ok = picked == q["answer"]
    if ok:
        print(f"  {C.G}DUNG{C.X}")
    else:
        print(f"  {C.R}SAI{C.X} - dap an: {q['choices'][q['answer']]}")
    return ok


def ask_open(q: dict) -> bool:
    print(f"  {C.DIM}(tu tra loi, go xong an Enter){C.X}")
    mine = ask_line("  > ")
    print(f"\n  {C.B}Dap an tham khao:{C.X} {q['answer']}")
    if q.get("keywords"):
        hit = [k for k in q["keywords"] if k.lower() in mine.lower()]
        print(f"  {C.DIM}Tu khoa trung: {len(hit)}/{len(q['keywords'])} {hit}{C.X}")
    v = ask_line("  Ban tra loi dung khong? (y/n): ").lower()
    return v.startswith("y")


def ask_recall(q: dict) -> bool:
    """Cau hoi nho lai: hien cau hoi, tu danh gia sau khi lat dap an."""
    ask_line(f"  {C.DIM}Nghi 10 giay roi an Enter de lat dap an...{C.X}")
    print(f"\n  {C.B}Dap an:{C.X} {q['answer']}")
    v = ask_line("  Ban nho duoc? (y/n): ").lower()
    return v.startswith("y")


ASKERS = {"mcq": ask_mcq, "open": ask_open, "recall": ask_recall}


def run_session(qs: list[dict], prog: dict, label: str, record: bool = True) -> tuple[int, int]:
    if not qs:
        print(f"{C.G}Khong co cau nao den han. Nghi ngoi.{C.X}")
        return 0, 0
    random.shuffle(qs)
    right = 0
    wrong_list = []
    for i, q in enumerate(qs, 1):
        rule(f"[{i}/{len(qs)}] Ngay {q['day']} - {q.get('topic', '')}")
        print(f"\n{C.BOLD}{q['q']}{C.X}\n")
        ok = ASKERS.get(q.get("type", "mcq"), ask_mcq)(q)
        if q.get("explain"):
            print(f"  {C.DIM}> {q['explain']}{C.X}")
        if record:
            schedule(card_of(prog, q["id"]), ok)
        if ok:
            right += 1
        else:
            wrong_list.append(q)
    rule("KET QUA")
    pct = right * 100 // len(qs)
    color = C.G if pct >= 80 else C.Y if pct >= 60 else C.R
    print(f"{label}: {color}{right}/{len(qs)} = {pct}%{C.X}")
    if pct >= 80:
        print(f"{C.G}PASS - du dieu kien sang ngay moi.{C.X}")
    else:
        print(f"{C.Y}CHUA PASS - can >= 80%. Doc lai phan ly thuyet roi chay lai.{C.X}")
    if wrong_list:
        print(f"\n{C.DIM}Cau con sai:{C.X}")
        for q in wrong_list:
            print(f"  - [ngay {q['day']}] {q['q'][:70]}")
    if record:
        prog["sessions"].append(
            {"date": today(), "label": label, "right": right, "total": len(qs)}
        )
        save_progress(prog)
    return right, len(qs)


# ---------------------------------------------------------------- subcommands
def cmd_day(day: int, prog: dict) -> None:
    bank = load_bank(day)
    if not bank:
        print(f"Chua co ngan hang cau hoi cho ngay {day}.")
        return
    qs = questions_for([day])
    run_session(qs, prog, f"Quiz ngay {day} - {bank.get('title', '')}")


def cmd_review(prog: dict, limit: int) -> None:
    qs = [q for q in questions_for(all_days()) if is_due(card_of(prog, q["id"])) and card_of(prog, q["id"])["seen"] > 0]
    if len(qs) > limit:
        qs.sort(key=lambda q: (prog["cards"][q["id"]]["box"], prog["cards"][q["id"]]["due"]))
        qs = qs[:limit]
    run_session(qs, prog, "On tap den han")


def cmd_exam(a: int, b: int, prog: dict) -> None:
    qs = questions_for([d for d in all_days() if a <= d <= b])
    print(f"THI TONG KET ngay {a}-{b}: {len(qs)} cau. Khong duoc mo tai lieu.")
    run_session(qs, prog, f"Exam {a}-{b}", record=True)


def cmd_weak(prog: dict) -> None:
    cards = [(qid, c) for qid, c in prog["cards"].items() if c["wrong"] > 0]
    cards.sort(key=lambda x: (-x[1]["wrong"], x[1]["box"]))
    index = {q["id"]: q for q in questions_for(all_days())}
    rule("10 CAU YEU NHAT")
    for qid, c in cards[:10]:
        q = index.get(qid)
        if q:
            print(f"  sai {c['wrong']}x | box {c['box']} | ngay {q['day']} | {q['q'][:60]}")
    if not cards:
        print("  Chua co cau nao sai. Hoac ban chua hoc du nhieu.")


def cmd_stats(prog: dict) -> None:
    cards = prog["cards"]
    total_q = len(questions_for(all_days()))
    seen = len(cards)
    boxes = {b: 0 for b in range(1, MAX_BOX + 1)}
    for c in cards.values():
        boxes[c["box"]] += 1
    due = sum(1 for c in cards.values() if is_due(c))
    mastered = boxes[5] + boxes[6]
    rule("THONG KE TRI NHO")
    print(f"  Tong cau hoi trong he thong : {total_q}")
    print(f"  Da hoc                      : {seen} ({seen * 100 // max(total_q, 1)}%)")
    print(f"  Da thuoc (box 5-6)          : {mastered}")
    print(f"  Den han hom nay             : {due}")
    print("\n  Phan bo hop Leitner:")
    for b in range(1, MAX_BOX + 1):
        bar = "#" * min(boxes[b], 40)
        print(f"    box {b} ({INTERVALS[b]:>2}d): {boxes[b]:>3} {bar}")
    recent = prog.get("sessions", [])[-7:]
    if recent:
        print("\n  7 phien gan nhat:")
        for s in recent:
            print(f"    {s['date']}  {s['label'][:34]:<34} {s['right']}/{s['total']}")


def cmd_doctor() -> None:
    rule("DOCTOR")
    print(f"  [ok] python {sys.version.split()[0]}")
    env = ROOT.parent / ".env"
    print(f"  [{'ok' if env.exists() else '--'}] .env {'found' if env.exists() else 'CHUA CO (copy tu .env.example)'}")
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        val = os.environ.get(k)
        if not val and env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith(k + "=") and line.split("=", 1)[1].strip():
                    val = "from .env"
        print(f"  [{'ok' if val else '--'}] {k} {'set' if val else 'chua dien'}")
    days = all_days()
    print(f"  [{'ok' if days else '--'}] quiz bank: {len(days)} ngay ({min(days) if days else '-'}..{max(days) if days else '-'})")
    for mod in ("dotenv", "pydantic", "anthropic"):
        try:
            __import__(mod)
            print(f"  [ok] {mod}")
        except ImportError:
            print(f"  [--] {mod} chua cai (pip install -r requirements.txt)")


def main() -> None:
    p = argparse.ArgumentParser(description="LeanAI quiz - spaced repetition")
    p.add_argument("--day", type=int, help="hoc quiz cua 1 ngay")
    p.add_argument("--review", action="store_true", help="on cac cau den han")
    p.add_argument("--exam", nargs=2, type=int, metavar=("FROM", "TO"))
    p.add_argument("--stats", action="store_true")
    p.add_argument("--weak", action="store_true")
    p.add_argument("--doctor", action="store_true")
    p.add_argument("--limit", type=int, default=25, help="so cau toi da moi phien on")
    p.add_argument("--reset", action="store_true", help="xoa toan bo tien do")
    args = p.parse_args()

    if args.doctor:
        return cmd_doctor()
    prog = load_progress()
    if args.reset:
        if ask_line("Xoa toan bo tien do quiz? (go 'yes'): ") == "yes":
            PROGRESS.unlink(missing_ok=True)
            print("Da xoa.")
        return
    if args.day:
        cmd_day(args.day, prog)
    elif args.review:
        cmd_review(prog, args.limit)
    elif args.exam:
        cmd_exam(args.exam[0], args.exam[1], prog)
    elif args.weak:
        cmd_weak(prog)
    elif args.stats:
        cmd_stats(prog)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
