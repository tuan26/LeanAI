#!/usr/bin/env python
"""LeanAI - thanh tien trinh hoc 90 ngay.

    python track.py                      # xem bang tien trinh
    python track.py --done 5             # danh dau ngay 5 PASS
    python track.py --done 5 --cost 0.12 --minutes 135 --note "kho phan embedding"
    python track.py --fail 6 --note "chua xong bai tap 2"
    python track.py --undo 5             # xoa danh dau
    python track.py --html               # xuat progress/dashboard.html
    python track.py --week               # bao cao 7 ngay gan nhat
    python track.py --budget 40          # dat ngan sach USD
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATUS = ROOT / "progress" / "status.json"
QUIZ_PROGRESS = ROOT / "quiz" / "progress.json"
QUIZ_BANK = ROOT / "quiz" / "bank"
CURRICULUM = ROOT / "curriculum"
HTML_OUT = ROOT / "progress" / "dashboard.html"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PHASES = [
    (1, "AI Fundamentals", 1, 14),
    (2, "LLM Engineering", 15, 30),
    (3, "RAG", 31, 50),
    (4, "AI Agent", 51, 65),
    (5, "AI Engineering", 66, 75),
    (6, "AI SaaS - Capstone", 76, 90),
]

MILESTONES = {
    14: "AI Explanation Engine",
    21: "CLI Chatbot",
    30: "AI Business Analyst",
    37: "Mini RAG",
    44: "Ingestion Pipeline",
    50: "Company Knowledge AI",
    65: "Research Agent",
    90: "CareDesk-AI - DEMO DAY",
}

MAX_DEBT = 2


class C:
    G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"
    CY = "\033[96m"; DIM = "\033[2m"; BOLD = "\033[1m"; X = "\033[0m"


# ------------------------------------------------------------------ dữ liệu
def load_status() -> dict:
    if STATUS.exists():
        try:
            return json.loads(STATUS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"{C.Y}! status.json hỏng, tạo mới{C.X}")
    return {"days": {}, "budget_usd": 40.0, "started": ""}


def save_status(s: dict) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def day_titles() -> dict[int, str]:
    out: dict[int, str] = {}
    for f in CURRICULUM.glob("phase*/day*.md"):
        n = int(f.stem[3:])
        first = f.read_text(encoding="utf-8", errors="replace").splitlines()[0]
        m = re.match(r"#\s*NGÀY\s*\d+\s*[—-]\s*(.+)", first.strip())
        out[n] = m.group(1).strip() if m else f.stem
    return out


def quiz_stats() -> dict:
    total_q = sum(len(json.loads(f.read_text(encoding="utf-8"))["questions"])
                  for f in QUIZ_BANK.glob("day*.json"))
    if not QUIZ_PROGRESS.exists():
        return {"total": total_q, "seen": 0, "mastered": 0, "due": 0,
                "sessions": [], "by_day": {}}
    p = json.loads(QUIZ_PROGRESS.read_text(encoding="utf-8"))
    cards = p.get("cards", {})
    today = dt.date.today().isoformat()
    by_day: dict[int, dict] = {}
    for qid, c in cards.items():
        m = re.match(r"d(\d+)q", qid)
        if not m:
            continue
        d = by_day.setdefault(int(m.group(1)), {"seen": 0, "mastered": 0})
        d["seen"] += 1
        d["mastered"] += c.get("box", 1) >= 5
    return {
        "total": total_q,
        "seen": len(cards),
        "mastered": sum(1 for c in cards.values() if c.get("box", 1) >= 5),
        "due": sum(1 for c in cards.values() if c.get("due", today) <= today),
        "sessions": p.get("sessions", []),
        "by_day": by_day,
    }


def git_commits() -> int:
    try:
        r = subprocess.run(["git", "rev-list", "--count", "HEAD"],
                           cwd=ROOT, capture_output=True, text=True, timeout=10)
        return int(r.stdout.strip()) if r.returncode == 0 else 0
    except Exception:
        return 0


# ------------------------------------------------------------------ tính toán
def analyse(status: dict, qz: dict) -> dict:
    days = {int(k): v for k, v in status.get("days", {}).items()}
    passed = sorted(d for d, v in days.items() if v.get("status") == "pass")
    failed = sorted(d for d, v in days.items() if v.get("status") == "fail")
    furthest = max(passed + failed, default=0)

    # nợ = ngày <= mốc xa nhất mà chưa PASS
    debt = [d for d in range(1, furthest + 1) if d not in passed]

    # chuỗi ngày học liên tiếp (theo lịch)
    dates = sorted({v["date"] for v in days.values() if v.get("date")})
    streak = 0
    if dates:
        cur = dt.date.fromisoformat(dates[-1])
        gap = (dt.date.today() - cur).days
        if gap <= 1:
            streak = 1
            for prev in reversed(dates[:-1]):
                p = dt.date.fromisoformat(prev)
                if (cur - p).days == 1:
                    streak += 1
                    cur = p
                elif (cur - p).days == 0:
                    continue
                else:
                    break

    cost = sum(float(v.get("cost", 0) or 0) for v in days.values())
    minutes = sum(int(v.get("minutes", 0) or 0) for v in days.values())

    per_phase = []
    for num, name, lo, hi in PHASES:
        total = hi - lo + 1
        done = sum(1 for d in passed if lo <= d <= hi)
        per_phase.append({"num": num, "name": name, "lo": lo, "hi": hi,
                          "total": total, "done": done,
                          "pct": done / total})

    next_day = next((d for d in range(1, 91) if d not in passed), None)
    if debt and len(debt) > MAX_DEBT:
        next_day = debt[0]

    return {"passed": passed, "failed": failed, "debt": debt, "streak": streak,
            "cost": cost, "minutes": minutes, "per_phase": per_phase,
            "next_day": next_day, "days": days, "furthest": furthest}


# ------------------------------------------------------------------ hiển thị
def bar(pct: float, width: int = 30, fill: str = "█", empty: str = "░") -> str:
    n = int(round(pct * width))
    return fill * n + empty * (width - n)


def colour_for(pct: float) -> str:
    return C.G if pct >= 0.99 else C.CY if pct > 0 else C.DIM


def render_terminal(status: dict, qz: dict, a: dict, titles: dict) -> None:
    done, total = len(a["passed"]), 90
    pct = done / total
    budget = float(status.get("budget_usd", 40.0))

    print()
    print(f"{C.BOLD}  LeanAI — TIẾN TRÌNH 90 NGÀY{C.X}")
    print(f"  {C.DIM}{'─' * 64}{C.X}")

    col = colour_for(pct)
    print(f"\n  {col}{bar(pct, 44)}{C.X}  {C.BOLD}{done}/90{C.X}  ({pct:.0%})")
    if a["next_day"]:
        print(f"  {C.DIM}Tiếp theo: Ngày {a['next_day']} — "
              f"{titles.get(a['next_day'], '')}{C.X}")
    else:
        print(f"  {C.G}{C.BOLD}Hoàn thành toàn bộ 90 ngày.{C.X}")

    # ---- phase ----
    print(f"\n  {C.BOLD}Theo giai đoạn{C.X}")
    for p in a["per_phase"]:
        c = colour_for(p["pct"])
        mark = "✓" if p["pct"] >= 0.999 else " "
        print(f"   {mark} P{p['num']} {p['name']:<22} {c}{bar(p['pct'], 22)}{C.X} "
              f"{p['done']:>2}/{p['total']:<2}")

    # ---- chỉ số ----
    mastery = qz["mastered"] / qz["total"] if qz["total"] else 0
    seen_pct = qz["seen"] / qz["total"] if qz["total"] else 0
    cost_pct = min(a["cost"] / budget, 1.0) if budget else 0
    commits = git_commits()
    hours = a["minutes"] / 60

    print(f"\n  {C.BOLD}Chỉ số{C.X}")
    print(f"   Quiz đã thuộc      {colour_for(mastery)}{bar(mastery, 22)}{C.X} "
          f"{qz['mastered']:>3}/{qz['total']} ({mastery:.0%})")
    print(f"   Quiz đã học        {C.DIM}{bar(seen_pct, 22)}{C.X} "
          f"{qz['seen']:>3}/{qz['total']} ({seen_pct:.0%})")
    cc = C.R if cost_pct > 0.9 else C.Y if cost_pct > 0.7 else C.G
    print(f"   Ngân sách API      {cc}{bar(cost_pct, 22)}{C.X} "
          f"${a['cost']:.2f}/${budget:.0f}")
    print(f"   Commit             {commits:>3}   "
          f"Giờ học {hours:>5.1f}h   "
          f"Chuỗi {C.Y}{a['streak']}{C.X} ngày")
    if qz["due"]:
        print(f"   {C.Y}⚠ {qz['due']} câu quiz đến hạn ôn "
              f"— chạy: python quiz/quiz.py --review{C.X}")

    # ---- nợ ----
    if a["debt"]:
        col = C.R if len(a["debt"]) > MAX_DEBT else C.Y
        print(f"\n  {col}{C.BOLD}Nợ {len(a['debt'])} ngày:{C.X} "
              f"{', '.join(str(d) for d in a['debt'][:10])}"
              f"{' ...' if len(a['debt']) > 10 else ''}")
        if len(a["debt"]) > MAX_DEBT:
            print(f"  {C.R}→ Quá {MAX_DEBT} ngày nợ. DỪNG học mới, "
                  f"quay lại Ngày {a['debt'][0]}.{C.X}")

    # ---- mốc sản phẩm ----
    print(f"\n  {C.BOLD}Mốc sản phẩm{C.X}")
    for d, name in MILESTONES.items():
        ok = d in a["passed"]
        icon = f"{C.G}●{C.X}" if ok else f"{C.DIM}○{C.X}"
        label = name if ok else f"{C.DIM}{name}{C.X}"
        print(f"   {icon} Ngày {d:>2}  {label}")

    # ---- hoạt động gần đây ----
    recent = sorted(((d, v) for d, v in a["days"].items() if v.get("date")),
                    key=lambda x: (x[1]["date"], x[0]))[-5:]
    if recent:
        print(f"\n  {C.BOLD}5 ngày gần nhất{C.X}")
        for d, v in recent:
            st = f"{C.G}PASS{C.X}" if v["status"] == "pass" else f"{C.R}FAIL{C.X}"
            extra = []
            if v.get("minutes"):
                extra.append(f"{v['minutes']}'")
            if v.get("cost"):
                extra.append(f"${float(v['cost']):.3f}")
            print(f"   {v['date']}  Ngày {d:>2}  {st}  "
                  f"{C.DIM}{' · '.join(extra)}  {v.get('note', '')[:38]}{C.X}")

    print(f"\n  {C.DIM}Đánh dấu xong: python track.py --done <N> "
          f"[--cost 0.1 --minutes 120 --note \"...\"]{C.X}")
    print(f"  {C.DIM}Xuất dashboard: python track.py --html{C.X}\n")


def render_week(a: dict, qz: dict, titles: dict) -> None:
    today = dt.date.today()
    print(f"\n{C.BOLD}  BÁO CÁO 7 NGÀY{C.X}\n  {C.DIM}{'─'*50}{C.X}")
    total_min = total_cost = 0
    n_days = 0
    for i in range(6, -1, -1):
        d = today - dt.timedelta(days=i)
        iso = d.isoformat()
        entries = [(k, v) for k, v in a["days"].items() if v.get("date") == iso]
        label = f"{d.strftime('%a %d/%m')}"
        if not entries:
            print(f"   {label}  {C.DIM}—{C.X}")
            continue
        n_days += 1
        for k, v in sorted(entries):
            mins = int(v.get("minutes", 0) or 0)
            cost = float(v.get("cost", 0) or 0)
            total_min += mins
            total_cost += cost
            st = f"{C.G}✓{C.X}" if v["status"] == "pass" else f"{C.R}✗{C.X}"
            print(f"   {label}  {st} Ngày {k:>2} {titles.get(k,'')[:26]:<27}"
                  f"{C.DIM}{mins:>4}'  ${cost:.3f}{C.X}")
    sess = [s for s in qz["sessions"] if s["date"] >= (today - dt.timedelta(days=6)).isoformat()]
    right = sum(s["right"] for s in sess)
    tot = sum(s["total"] for s in sess)
    print(f"\n   Học {n_days}/7 ngày · {total_min/60:.1f}h · ${total_cost:.3f}")
    if tot:
        print(f"   Quiz tuần: {right}/{tot} = {right/tot:.0%}")
    pace = len(a["passed"])
    print(f"   Nhịp hiện tại: {n_days} ngày/tuần → còn {90-pace} ngày "
          f"≈ {(90-pace)/max(n_days,1):.0f} tuần nữa\n")


# ------------------------------------------------------------------ HTML
HTML_TMPL = """<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LeanAI Progress</title>
<style>
:root{--bg:#f7f8fa;--card:#fff;--tx:#1a1d23;--mut:#6b7280;--line:#e5e7eb;
--ok:#10b981;--cy:#0ea5e9;--wa:#f59e0b;--er:#ef4444;--track:#e9ecf1}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#0f1115;--card:#171a21;--tx:#e6e8ec;--mut:#9aa3af;--line:#252a33;--track:#232832}}
:root[data-theme=dark]{--bg:#0f1115;--card:#171a21;--tx:#e6e8ec;--mut:#9aa3af;
--line:#252a33;--track:#232832}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 -apple-system,
BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:24px 16px}
.wrap{max-width:900px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--mut);font-size:13px;margin-bottom:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:20px;margin-bottom:16px}
.big{font-size:40px;font-weight:700;line-height:1}
.big span{font-size:18px;color:var(--mut);font-weight:500}
.track{height:12px;background:var(--track);border-radius:99px;overflow:hidden;margin:14px 0 6px}
.fill{height:100%;border-radius:99px;transition:width .4s}
.row{display:flex;align-items:center;gap:12px;margin:9px 0;font-size:14px}
.row .nm{flex:0 0 190px;color:var(--mut)}
.row .tr{flex:1;height:8px;background:var(--track);border-radius:99px;overflow:hidden}
.row .vl{flex:0 0 78px;text-align:right;font-variant-numeric:tabular-nums;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.stat .k{color:var(--mut);font-size:12px;margin-bottom:4px}
.stat .v{font-size:22px;font-weight:600}
h2{font-size:14px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);
margin:0 0 14px}
.ms{display:flex;align-items:center;gap:10px;padding:7px 0;font-size:14px;
border-bottom:1px solid var(--line)}
.ms:last-child{border:0}
.dot{width:9px;height:9px;border-radius:99px;flex:0 0 9px}
.muted{color:var(--mut)}
.warn{background:rgba(239,68,68,.1);border-color:rgba(239,68,68,.35)}
table{width:100%;border-collapse:collapse;font-size:13px}
td{padding:6px 4px;border-bottom:1px solid var(--line)}
td:last-child{text-align:right;color:var(--mut)}
.days{display:flex;flex-wrap:wrap;gap:3px;margin-top:6px}
.d{width:15px;height:15px;border-radius:3px;background:var(--track);
font-size:0;position:relative}
.d.p{background:var(--ok)}.d.f{background:var(--er)}.d.n{outline:2px solid var(--cy);outline-offset:1px}
</style></head><body><div class="wrap">
<h1>LeanAI — Tiến trình 90 ngày</h1>
<div class="sub">Cập nhật __UPDATED__ · __NEXT__</div>

<div class="card">
  <div class="big">__DONE__<span>/90 ngày</span></div>
  <div class="track"><div class="fill" style="width:__PCT__%;background:var(--ok)"></div></div>
  <div class="muted" style="font-size:13px">__PCT__% hoàn thành</div>
  <div class="days">__DAYGRID__</div>
</div>

<div class="grid" style="margin-bottom:16px">__STATS__</div>

<div class="card"><h2>Theo giai đoạn</h2>__PHASES__</div>

<div class="card"><h2>Mốc sản phẩm</h2>__MILESTONES__</div>

__DEBT__

<div class="card"><h2>Hoạt động gần đây</h2><table>__RECENT__</table></div>

<div class="sub" style="margin-top:18px">Tạo bởi <code>python track.py --html</code></div>
</div></body></html>"""


def render_html(status: dict, qz: dict, a: dict, titles: dict) -> Path:
    done = len(a["passed"])
    pct = round(done / 90 * 100)
    budget = float(status.get("budget_usd", 40.0))
    mastery = qz["mastered"] / qz["total"] if qz["total"] else 0

    grid = []
    for d in range(1, 91):
        cls = "d p" if d in a["passed"] else "d f" if d in a["failed"] else "d"
        if d == a["next_day"]:
            cls += " n"
        grid.append(f'<div class="{cls}" title="Ngày {d}: {titles.get(d,"")}"></div>')

    stats = []
    for k, v in [
        ("Quiz đã thuộc", f"{qz['mastered']}/{qz['total']}"),
        ("Tỉ lệ thuộc", f"{mastery:.0%}"),
        ("Chi phí API", f"${a['cost']:.2f} / ${budget:.0f}"),
        ("Giờ học", f"{a['minutes']/60:.1f}h"),
        ("Chuỗi ngày", f"{a['streak']}"),
        ("Commit", f"{git_commits()}"),
    ]:
        stats.append(f'<div class="stat"><div class="k">{k}</div><div class="v">{v}</div></div>')

    phases = []
    for p in a["per_phase"]:
        colr = "var(--ok)" if p["pct"] >= 0.999 else "var(--cy)"
        phases.append(
            f'<div class="row"><div class="nm">P{p["num"]} · {p["name"]}</div>'
            f'<div class="tr"><div class="fill" style="width:{p["pct"]*100:.0f}%;'
            f'background:{colr}"></div></div>'
            f'<div class="vl">{p["done"]}/{p["total"]}</div></div>')

    ms = []
    for d, name in MILESTONES.items():
        ok = d in a["passed"]
        dot = "var(--ok)" if ok else "var(--track)"
        cls = "" if ok else ' class="muted"'
        ms.append(f'<div class="ms"><div class="dot" style="background:{dot}"></div>'
                  f'<div{cls}>Ngày {d} — {name}</div></div>')

    debt_html = ""
    if a["debt"]:
        over = len(a["debt"]) > MAX_DEBT
        debt_html = (f'<div class="card{" warn" if over else ""}"><h2>Nợ</h2>'
                     f'<div>{len(a["debt"])} ngày chưa PASS: '
                     f'{", ".join(str(x) for x in a["debt"][:15])}</div>'
                     + (f'<div style="margin-top:8px;color:var(--er)">Quá {MAX_DEBT} '
                        f'ngày nợ — dừng học mới, quay lại Ngày {a["debt"][0]}.</div>'
                        if over else "") + '</div>')

    recent = sorted(((d, v) for d, v in a["days"].items() if v.get("date")),
                    key=lambda x: (x[1]["date"], x[0]))[-8:]
    rows = []
    for d, v in reversed(recent):
        ok = v["status"] == "pass"
        rows.append(
            f'<tr><td>{v["date"]}</td><td>Ngày {d} — {titles.get(d,"")}</td>'
            f'<td style="color:{"var(--ok)" if ok else "var(--er)"}">'
            f'{"PASS" if ok else "FAIL"}</td>'
            f'<td>{v.get("minutes",0)}\' · ${float(v.get("cost",0) or 0):.3f}</td></tr>')
    if not rows:
        rows.append('<tr><td colspan="4" class="muted">Chưa có dữ liệu — '
                    'dùng <code>python track.py --done 1</code></td></tr>')

    nxt = (f"Tiếp theo: Ngày {a['next_day']} — {titles.get(a['next_day'],'')}"
           if a["next_day"] else "Đã hoàn thành 90 ngày 🎉")

    html = (HTML_TMPL
            .replace("__UPDATED__", dt.datetime.now().strftime("%d/%m/%Y %H:%M"))
            .replace("__NEXT__", nxt)
            .replace("__DONE__", str(done))
            .replace("__PCT__", str(pct))
            .replace("__DAYGRID__", "".join(grid))
            .replace("__STATS__", "".join(stats))
            .replace("__PHASES__", "".join(phases))
            .replace("__MILESTONES__", "".join(ms))
            .replace("__DEBT__", debt_html)
            .replace("__RECENT__", "".join(rows)))

    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(html, encoding="utf-8")
    return HTML_OUT


# ------------------------------------------------------------------ lệnh
def cmd_mark(st: dict, day: int, ok: bool, args, qz: dict) -> None:
    if not 1 <= day <= 90:
        raise SystemExit("Ngày phải trong khoảng 1..90")
    qd = qz["by_day"].get(day, {"seen": 0})
    if ok and qd["seen"] == 0:
        print(f"{C.Y}⚠ Chưa làm quiz Ngày {day}. Chạy: "
              f"python quiz/quiz.py --day {day}{C.X}")
    st.setdefault("days", {})[str(day)] = {
        "status": "pass" if ok else "fail",
        "date": args.date or dt.date.today().isoformat(),
        "cost": args.cost, "minutes": args.minutes, "note": args.note or "",
    }
    if not st.get("started"):
        st["started"] = dt.date.today().isoformat()
    save_status(st)
    icon = f"{C.G}PASS{C.X}" if ok else f"{C.R}FAIL{C.X}"
    print(f"  Ngày {day}: {icon}" + (f"  {args.note}" if args.note else ""))


def main() -> None:
    p = argparse.ArgumentParser(description="LeanAI - thanh tiến trình 90 ngày")
    p.add_argument("--done", type=int, metavar="N", help="đánh dấu ngày N là PASS")
    p.add_argument("--fail", type=int, metavar="N", help="đánh dấu ngày N là FAIL")
    p.add_argument("--undo", type=int, metavar="N", help="xoá đánh dấu ngày N")
    p.add_argument("--cost", type=float, default=0.0, help="chi phí API ngày đó (USD)")
    p.add_argument("--minutes", type=int, default=0, help="số phút đã học")
    p.add_argument("--note", default="", help="ghi chú ngắn")
    p.add_argument("--date", default="", help="ngày thực tế YYYY-MM-DD (mặc định hôm nay)")
    p.add_argument("--budget", type=float, help="đặt ngân sách API (USD)")
    p.add_argument("--html", action="store_true", help="xuất progress/dashboard.html")
    p.add_argument("--week", action="store_true", help="báo cáo 7 ngày")
    p.add_argument("--json", action="store_true", help="in dữ liệu JSON")
    args = p.parse_args()

    st = load_status()
    qz = quiz_stats()
    titles = day_titles()

    if args.budget is not None:
        st["budget_usd"] = args.budget
        save_status(st)
        print(f"  Ngân sách API: ${args.budget:.0f}")
    if args.done:
        cmd_mark(st, args.done, True, args, qz)
    if args.fail:
        cmd_mark(st, args.fail, False, args, qz)
    if args.undo:
        if st.get("days", {}).pop(str(args.undo), None):
            save_status(st)
            print(f"  Đã xoá đánh dấu Ngày {args.undo}")
        else:
            print(f"  Ngày {args.undo} chưa được đánh dấu")

    a = analyse(st, qz)

    if args.json:
        print(json.dumps({"done": len(a["passed"]), "debt": a["debt"],
                          "streak": a["streak"], "cost": a["cost"],
                          "quiz_mastered": qz["mastered"], "quiz_total": qz["total"],
                          "next_day": a["next_day"]}, ensure_ascii=False, indent=2))
        return
    if args.week:
        render_week(a, qz, titles)
        return
    if args.html:
        out = render_html(st, qz, a, titles)
        print(f"  Đã tạo {out}")
        print(f"  Mở bằng: start {out}")
        return

    render_terminal(st, qz, a, titles)


if __name__ == "__main__":
    main()
