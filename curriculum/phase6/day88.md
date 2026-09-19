# NGÀY 88 — Dashboard

> Phase 6 · 15' thiết kế — 105' code

## 🎯 Mục tiêu

Dashboard **5 chỉ số** mà chủ phòng khám thật sự quan tâm — ít nhưng hữu ích.

---

## 1. Thiết kế (15 phút)

### Năm chỉ số (không thêm)

```
┌──────────────────────────────────────────────────────────┐
│  Cơ hội doanh thu phát hiện          128                 │
│  Giá trị tiềm năng                   420.000.000đ        │
│  Đã duyệt gửi                        73                  │
│  Tin nhắn đã gửi                     51                  │
│  Doanh thu thu hồi được              86.000.000đ  ↑ 12%  │
└──────────────────────────────────────────────────────────┘
```

> **Chỉ số cuối cùng là lý do khách hàng trả tiền.** Bốn chỉ số đầu chỉ là quá trình.

### Vì sao không thêm chỉ số

Dashboard 20 chỉ số = không ai nhìn. Chủ phòng khám cần trả lời một câu: *"Tháng này hệ thống mang về bao nhiêu tiền?"*

Chỉ số kỹ thuật (latency, cost, token) để **màn hình riêng cho bạn**, không cho khách hàng.

### Đo doanh thu thu hồi thế nào

```
Tin nhắn gửi → khách đặt lịch trong 30 ngày → đến → doanh thu
                       ↑
              cần ghi nhận: opportunity_id trên booking
```

Nếu chưa tích hợp được phần mềm đặt lịch: cho nhân viên đánh dấu tay "khách này quay lại nhờ tin nhắn". Không hoàn hảo nhưng có còn hơn không.

---

## 2. Code (105 phút)

`backend/app/routers/metrics.py`:

```python
"""Chỉ số dashboard."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func

from ..db import tenant_session
from ..deps import Principal, require_permission
from ..models import Message, MsgStatus, Opportunity, OppStatus

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary")
def summary(days: int = Query(30, ge=1, le=365),
            p: Principal = Depends(require_permission("read_opportunities"))):
    since = date.today() - timedelta(days=days)
    prev_since = since - timedelta(days=days)

    with tenant_session(p.tenant_id) as db:
        def opp_stats(frm, to):
            q = db.query(
                func.count(Opportunity.id),
                func.coalesce(func.sum(Opportunity.estimated_value_vnd), 0),
                func.coalesce(func.sum(Opportunity.converted_value_vnd), 0),
            ).filter(Opportunity.detected_at >= frm, Opportunity.detected_at < to)
            return q.one()

        n_opp, potential, recovered = opp_stats(since, date.today() + timedelta(days=1))
        _, _, prev_recovered = opp_stats(prev_since, since)

        approved = db.query(func.count(Message.id)).filter(
            Message.created_at >= since,
            Message.status.in_([MsgStatus.APPROVED, MsgStatus.SENT])).scalar()
        sent = db.query(func.count(Message.id)).filter(
            Message.sent_at >= since, Message.status == MsgStatus.SENT).scalar()
        converted = db.query(func.count(Opportunity.id)).filter(
            Opportunity.detected_at >= since,
            Opportunity.status == OppStatus.CONVERTED).scalar()

        growth = ((recovered - prev_recovered) / prev_recovered * 100
                  if prev_recovered else None)

        return {
            "period_days": days,
            "opportunities_detected": n_opp,
            "potential_revenue_vnd": int(potential),
            "approved": approved,
            "messages_sent": sent,
            "recovered_revenue_vnd": int(recovered),
            "recovered_growth_pct": round(growth, 1) if growth is not None else None,
            "conversion_rate": round(converted / sent, 3) if sent else 0.0,
            "roi_note": "doanh thu thu hồi / chi phí AI — xem /metrics/ops",
        }


@router.get("/funnel")
def funnel(days: int = 30,
           p: Principal = Depends(require_permission("read_opportunities"))):
    since = date.today() - timedelta(days=days)
    with tenant_session(p.tenant_id) as db:
        rows = db.query(Opportunity.status, func.count(Opportunity.id)).filter(
            Opportunity.detected_at >= since).group_by(Opportunity.status).all()
        counts = {s.value: n for s, n in rows}
        order = ["new", "drafted", "pending_approval", "approved", "sent", "converted"]
        stages = [{"stage": s, "count": counts.get(s, 0)} for s in order]
        for i, st in enumerate(stages):
            prev = stages[i - 1]["count"] if i else st["count"]
            st["drop_rate"] = round(1 - st["count"] / prev, 3) if prev else 0.0
        return {"stages": stages,
                "biggest_drop": max(stages[1:], key=lambda x: x["drop_rate"],
                                    default=None)}


@router.get("/by-type")
def by_type(days: int = 30,
            p: Principal = Depends(require_permission("read_opportunities"))):
    since = date.today() - timedelta(days=days)
    with tenant_session(p.tenant_id) as db:
        rows = db.query(
            Opportunity.opp_type,
            func.count(Opportunity.id),
            func.coalesce(func.sum(Opportunity.estimated_value_vnd), 0),
            func.coalesce(func.sum(Opportunity.converted_value_vnd), 0),
        ).filter(Opportunity.detected_at >= since).group_by(Opportunity.opp_type).all()
        return [{"type": t.value, "count": n, "potential_vnd": int(pot),
                 "recovered_vnd": int(rec),
                 "conversion_value_rate": round(rec / pot, 3) if pot else 0.0}
                for t, n, pot, rec in rows]


@router.get("/ops")
def ops_metrics(days: int = 7,
                p: Principal = Depends(require_permission("view_costs"))):
    """Chỉ số kỹ thuật — chỉ quản lý trở lên xem."""
    import json
    from pathlib import Path
    costs, latencies, errors = 0.0, [], 0
    for i in range(days):
        f = Path("logs") / f"{date.today() - timedelta(days=i)}.jsonl"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            costs += float(r.get("cost", 0) or 0)
            if r.get("latency"):
                latencies.append(float(r["latency"]))
            if r.get("event", "").endswith("error"):
                errors += 1
    latencies.sort()
    return {"days": days, "ai_cost_usd": round(costs, 4),
            "ai_cost_vnd": int(costs * 25000),
            "requests": len(latencies), "errors": errors,
            "latency_p50": round(latencies[len(latencies)//2], 2) if latencies else 0,
            "latency_p95": round(latencies[int(len(latencies)*0.95)-1], 2)
            if latencies else 0}
```

### Frontend tối giản

`frontend/app/dashboard/page.tsx` (Next.js):

```tsx
async function getMetrics() {
  const r = await fetch(`${process.env.API_URL}/metrics/summary?days=30`,
                        { cache: "no-store", credentials: "include" });
  return r.json();
}

const vnd = (n: number) => new Intl.NumberFormat("vi-VN").format(n) + "đ";

export default async function Dashboard() {
  const m = await getMetrics();
  const cards = [
    { label: "Cơ hội doanh thu", value: m.opportunities_detected },
    { label: "Giá trị tiềm năng", value: vnd(m.potential_revenue_vnd) },
    { label: "Đã duyệt", value: m.approved },
    { label: "Tin nhắn đã gửi", value: m.messages_sent },
    { label: "Doanh thu thu hồi", value: vnd(m.recovered_revenue_vnd),
      delta: m.recovered_growth_pct, highlight: true },
  ];
  return (
    <main className="p-8">
      <h1 className="text-2xl font-semibold mb-6">Tổng quan 30 ngày</h1>
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {cards.map(c => (
          <div key={c.label}
               className={`rounded-xl border p-5 ${c.highlight ? "bg-emerald-50 border-emerald-200" : "bg-white"}`}>
            <div className="text-sm text-gray-500">{c.label}</div>
            <div className="text-2xl font-bold mt-1">{c.value}</div>
            {c.delta != null && (
              <div className={`text-sm mt-1 ${c.delta >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                {c.delta >= 0 ? "↑" : "↓"} {Math.abs(c.delta)}% so với kỳ trước
              </div>
            )}
          </div>
        ))}
      </div>
    </main>
  );
}
```

---

## 3. PASS/FAIL

- [ ] Đúng 5 chỉ số trên dashboard chính, không thêm
- [ ] Doanh thu thu hồi hiển thị nổi bật + so sánh kỳ trước
- [ ] Phễu chuyển đổi chỉ ra được bước rơi nhiều nhất
- [ ] Chỉ số kỹ thuật tách riêng, chỉ quản lý trở lên xem
- [ ] Số liệu đúng với dữ liệu trong DB (đối chiếu tay 3 con số)
- [ ] Dashboard tải < 1 giây

---

## 4. Quiz + commit

```powershell
python quiz\quiz.py --day 88 ; python quiz\quiz.py --review
git add . ; git commit -m "day 88: dashboard"
```
