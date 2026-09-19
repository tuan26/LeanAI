# NGÀY 85 — Agent: detect → recommend

> Phase 6 · 15' thiết kế — 105' code

## 🎯 Mục tiêu

Job đêm chạy toàn bộ luồng: quét khách → phát hiện → chấm điểm → giải thích → đề xuất hành động. Chạy được trên 3.000 khách thật.

---

## 1. Thiết kế (15 phút)

### Đây là workflow, không phải agent tự do

Nhớ Ngày 60: các bước biết trước, thứ tự cố định, cần đoán được và kiểm toán được → **workflow**.

```
[1] SQL      : lọc 3.000 khách → ~80 ứng viên        (0 LLM, vài giây)
[2] CODE     : chấm điểm, xếp hạng                    (0 LLM)
[3] CODE     : lọc top N theo ngân sách               (0 LLM)
[4] LLM      : giải thích (song song)                 (N lời gọi)
[5] CODE     : quyết định kênh + thời điểm            (0 LLM)
[6] LLM      : soạn nháp tin nhắn (Ngày 86)           (N lời gọi)
[7] CODE     : guardrail + đưa vào hàng chờ duyệt     (0 LLM)
```

Chỉ 2/7 bước dùng LLM. Đây là lý do chi phí thấp.

### Ngân sách job

```
max_opportunities_per_run : 100      # không làm ngập hàng chờ duyệt
max_cost_per_run          : $0.50
max_duration              : 10 phút
```

Vượt ngân sách → dừng, ghi log, xử lý phần còn lại ở lần chạy sau.

---

## 2. Code (105 phút)

`backend/app/worker/nightly.py`:

```python
"""Job đêm: quét cơ hội và soạn nháp."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from leanai_core.logging import log_event
from leanai_core.reliability import JobRunner

from ..db import tenant_session
from ..models import (Message, MsgStatus, Opportunity, OppStatus, Tenant)
from ..services.detector import detect_all, persist, DetectionRules
from ..services.explainer import explain
from ..services.scoring import score_opportunity
from ..services.drafter import draft_message          # Ngày 86
from ..services.guards import check_business_rules    # Ngày 62 áp dụng


@dataclass
class JobBudget:
    max_opportunities: int = 100
    max_cost_usd: float = 0.50
    max_seconds: int = 600
    spent: float = 0.0
    started: float = field(default_factory=time.time)

    def exceeded(self) -> str | None:
        if self.spent > self.max_cost_usd:
            return f"vượt ngân sách ${self.max_cost_usd}"
        if time.time() - self.started > self.max_seconds:
            return f"vượt {self.max_seconds}s"
        return None


def run_for_tenant(tenant_id: str, today: date | None = None,
                   budget: JobBudget | None = None, dry_run: bool = False) -> dict:
    today = today or date.today()
    budget = budget or JobBudget()
    t0 = time.time()
    stats = {"tenant": tenant_id, "quét": 0, "phát hiện": 0, "xử lý": 0,
             "nháp tạo": 0, "bị chặn": 0, "lỗi": 0, "chi phí": 0.0}

    with tenant_session(tenant_id) as db:
        # [1] phát hiện — RULE
        found = detect_all(db, tenant_id, today, DetectionRules())
        stats["phát hiện"] = len(found)
        log_event("nightly_detect", tenant=tenant_id, found=len(found))

        if not dry_run:
            persist(db, tenant_id, found)

        # [2][3] chấm điểm + xếp hạng + cắt theo ngân sách
        ranked = []
        for o in found:
            s = score_opportunity(opp_type=o.opp_type,
                                  estimated_value_vnd=o.estimated_value_vnd,
                                  reason_data=o.reason_data)
            ranked.append((o, s))
        ranked.sort(key=lambda x: -x[1].expected_value_vnd)
        ranked = ranked[:budget.max_opportunities]

        # [4][5][6][7]
        for o, s in ranked:
            stop = budget.exceeded()
            if stop:
                log_event("nightly_budget_stop", tenant=tenant_id, reason=stop,
                          processed=stats["xử lý"])
                stats["dừng sớm"] = stop
                break
            try:
                # [4] giải thích
                ex = explain(o.reason_data, probability=s.probability,
                             expected_value=s.expected_value_vnd, factors=s.factors)
                budget.spent += ex.cost

                # [5] chọn kênh
                channel = o.reason_data.get("kenh_ua_thich", "zalo")
                if "không thích gọi" in (o.reason_data.get("ghi_chu") or "").lower():
                    channel = "zalo"

                # [6] soạn nháp
                draft = draft_message(o.reason_data, opp_type=o.opp_type,
                                      channel=channel, explanation=ex.text)
                budget.spent += draft.cost

                # [7] guardrail
                ok, issues = check_business_rules(
                    tenant_id=tenant_id, customer_id=o.customer_id,
                    message=draft.text, reason_data=o.reason_data, db=db)
                if not ok:
                    stats["bị chặn"] += 1
                    log_event("nightly_blocked", tenant=tenant_id,
                              customer=o.customer_id,
                              reasons=[i.reason for i in issues])
                    continue

                if not dry_run:
                    opp = db.query(Opportunity).filter(
                        Opportunity.tenant_id == tenant_id,
                        Opportunity.customer_id == o.customer_id,
                        Opportunity.opp_type == o.opp_type,
                        Opportunity.status == OppStatus.NEW).first()
                    if opp:
                        opp.explanation = ex.text
                        opp.confidence = int(s.probability * 100)
                        opp.status = OppStatus.PENDING_APPROVAL
                        db.add(Message(
                            tenant_id=tenant_id, opportunity_id=opp.id,
                            customer_id=o.customer_id, channel=channel,
                            draft_content=draft.text, status=MsgStatus.PENDING,
                            idempotency_key=f"{tenant_id}:{o.customer_id}:"
                                            f"{o.opp_type.value}:{today.isoformat()}"))
                        stats["nháp tạo"] += 1
                stats["xử lý"] += 1

            except Exception as e:
                stats["lỗi"] += 1
                log_event("nightly_error", tenant=tenant_id,
                          customer=o.customer_id, error=f"{type(e).__name__}: {e}")

        if not dry_run:
            db.commit()

    stats["chi phí"] = round(budget.spent, 5)
    stats["giây"] = round(time.time() - t0, 1)
    log_event("nightly_done", **stats)
    return stats


def run_all_tenants(dry_run: bool = False) -> list[dict]:
    from ..db import admin_session
    with admin_session() as db:
        tenants = [t.id for t in db.query(Tenant).all()]
    out = []
    for tid in tenants:
        print(f"\n=== {tid} ===")
        s = run_for_tenant(tid, dry_run=dry_run)
        print(json.dumps(s, ensure_ascii=False, indent=2))
        out.append(s)
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.tenant:
        print(json.dumps(run_for_tenant(a.tenant, dry_run=a.dry_run),
                         ensure_ascii=False, indent=2))
    else:
        run_all_tenants(dry_run=a.dry_run)
```

---

## 3. Việc phải làm

1. Chạy `--dry-run` trước trên 3.000 khách. Xem: phát hiện bao nhiêu, ước tính chi phí bao nhiêu.
2. Chạy thật trên `clinic_001`. Kiểm tra hàng chờ duyệt có nháp.
3. Chạy **lại lần 2** ngay — phải không tạo nháp trùng (idempotency key).
4. Đặt `max_cost_usd=0.01` → xác nhận job dừng sớm và ghi log rõ ràng.
5. Đo: chi phí/phòng khám/lần chạy. Nhân 30 ngày → chi phí tháng. So với bảng định giá Ngày 70.

---

## 4. PASS/FAIL

- [ ] Job chạy end-to-end trên 3.000 khách
- [ ] Chỉ ~2/7 bước dùng LLM
- [ ] Chạy 2 lần không tạo nháp trùng
- [ ] Ngân sách chi phí/thời gian được tôn trọng, dừng sớm có log
- [ ] Guardrail chặn được ca vi phạm, có ghi log lý do
- [ ] Lỗi một khách không làm chết cả job
- [ ] Chi phí thực tế khớp dự tính Ngày 70 (±30%)

---

## 5. Quiz + commit

```powershell
python -m app.worker.nightly --tenant clinic_001 --dry-run
python quiz\quiz.py --day 85 ; python quiz\quiz.py --review
git add . ; git commit -m "day 85: nightly opportunity workflow"
```
