# NGÀY 87 — Human approval + send

> Phase 6 · 15' thiết kế — 105' code

## 🎯 Mục tiêu

Màn hình duyệt hoàn chỉnh: **Approve / Edit / Reject** → gửi thật → ghi nhận kết quả.

---

## 1. Thiết kế (15 phút)

### Luồng đầy đủ

```
Nháp (pending)
   │
   ├─ Approve → guardrail lần cuối → gửi → sent → ghi nhận
   ├─ Edit    → lưu bản sửa → gửi → edited+sent → THU THẬP làm dữ liệu học
   └─ Reject  → bắt buộc nhập lý do → rejected → THU THẬP làm dữ liệu học
```

### Guardrail chạy **lần nữa** trước khi gửi

Giữa lúc soạn nháp (đêm) và lúc duyệt (sáng), tình hình có thể đổi: khách vừa đến, khách vừa khiếu nại, đã có người gửi tin. **Luôn kiểm tra lại tại thời điểm gửi.**

### Idempotency

Nhân viên bấm Approve hai lần (mạng chậm) → chỉ được gửi **một** tin.

---

## 2. Code (105 phút)

`backend/app/routers/messages.py`:

```python
"""Duyệt và gửi tin nhắn."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import tenant_session
from ..deps import Principal, require_permission
from ..models import (AuditLog, Customer, Message, MsgStatus, Opportunity, OppStatus)
from ..services.guards import check_business_rules
from ..services.sender import send_via_channel

router = APIRouter(prefix="/messages", tags=["messages"])


class EditIn(BaseModel):
    content: str = Field(min_length=10, max_length=600)


class RejectIn(BaseModel):
    reason: str = Field(min_length=5, description="bắt buộc — dùng để cải tiến AI")


@router.get("/pending")
def list_pending(p: Principal = Depends(require_permission("read_opportunities"))):
    """Sắp xếp theo rủi ro rồi giá trị — ca khó lên đầu."""
    with tenant_session(p.tenant_id) as db:
        rows = (db.query(Message, Opportunity, Customer)
                .join(Opportunity, Message.opportunity_id == Opportunity.id)
                .join(Customer, Message.customer_id == Customer.id)
                .filter(Message.status == MsgStatus.PENDING)
                .all())
        items = []
        for m, o, c in rows:
            flags = []
            if c.notes:
                flags.append(f"⚠ Ghi chú: {c.notes}")
            if o.estimated_value_vnd > 5_000_000:
                flags.append(f"💰 Giá trị lớn: {o.estimated_value_vnd:,}đ")
            if c.lifetime_value > 30_000_000:
                flags.append("⭐ Khách thân thiết")
            items.append({
                "message_id": m.id, "customer_name": c.full_name,
                "channel": m.channel, "content": m.draft_content,
                "explanation": o.explanation,
                "estimated_value": o.estimated_value_vnd,
                "confidence": o.confidence, "opp_type": o.opp_type.value,
                "risk_flags": flags, "created_at": m.created_at.isoformat()})
        items.sort(key=lambda x: (-len(x["risk_flags"]), -x["estimated_value"]))
        return items


def _finalize(db, p: Principal, m: Message, content: str, status: MsgStatus):
    """Guardrail lần cuối + gửi + ghi nhận."""
    import json
    opp = db.query(Opportunity).filter(Opportunity.id == m.opportunity_id).first()
    ok, issues = check_business_rules(
        tenant_id=p.tenant_id, customer_id=m.customer_id, message=content,
        reason_data=json.loads(opp.reason_data or "{}"), db=db)
    if not ok:
        raise HTTPException(422, {"message": "Guardrail chặn tại thời điểm gửi",
                                  "reasons": [i.reason for i in issues]})

    result = send_via_channel(channel=m.channel, customer_id=m.customer_id,
                              content=content, idempotency_key=m.idempotency_key,
                              tenant_id=p.tenant_id)
    m.final_content = content
    m.status = MsgStatus.SENT if result["status"] == "sent" else MsgStatus.FAILED
    m.reviewer_id = p.user_id
    m.sent_at = datetime.now(timezone.utc)
    opp.status = OppStatus.SENT
    db.add(AuditLog(tenant_id=p.tenant_id, user_id=p.user_id,
                    action=status.value, entity="message", entity_id=str(m.id),
                    detail=json.dumps({"channel": m.channel,
                                       "duplicate": result.get("duplicate", False)},
                                      ensure_ascii=False)))
    return result


@router.post("/{message_id}/approve")
def approve(message_id: int,
            p: Principal = Depends(require_permission("approve_message"))):
    with tenant_session(p.tenant_id) as db:
        m = db.query(Message).filter(Message.id == message_id).first()
        if not m:
            raise HTTPException(404, "Không tìm thấy tin nhắn")
        if m.status == MsgStatus.SENT:
            return {"status": "already_sent", "message": "Tin đã được gửi trước đó"}
        if m.status != MsgStatus.PENDING:
            raise HTTPException(409, f"Tin đang ở trạng thái {m.status.value}")
        result = _finalize(db, p, m, m.draft_content, MsgStatus.APPROVED)
        db.commit()
        return {"status": m.status.value, **result}


@router.post("/{message_id}/edit")
def edit_and_send(message_id: int, body: EditIn,
                  p: Principal = Depends(require_permission("approve_message"))):
    with tenant_session(p.tenant_id) as db:
        m = db.query(Message).filter(Message.id == message_id).first()
        if not m or m.status != MsgStatus.PENDING:
            raise HTTPException(409, "Tin không ở trạng thái chờ duyệt")
        result = _finalize(db, p, m, body.content, MsgStatus.EDITED)
        m.status = MsgStatus.SENT
        db.commit()
        return {"status": "sent_after_edit", **result}


@router.post("/{message_id}/reject")
def reject(message_id: int, body: RejectIn,
           p: Principal = Depends(require_permission("approve_message"))):
    with tenant_session(p.tenant_id) as db:
        m = db.query(Message).filter(Message.id == message_id).first()
        if not m or m.status != MsgStatus.PENDING:
            raise HTTPException(409, "Tin không ở trạng thái chờ duyệt")
        m.status = MsgStatus.REJECTED
        m.reject_reason = body.reason
        m.reviewer_id = p.user_id
        opp = db.query(Opportunity).filter(Opportunity.id == m.opportunity_id).first()
        opp.status = OppStatus.REJECTED
        db.add(AuditLog(tenant_id=p.tenant_id, user_id=p.user_id, action="reject",
                        entity="message", entity_id=str(m.id), detail=body.reason))
        db.commit()
        return {"status": "rejected"}


@router.get("/learning-samples")
def learning_samples(p: Principal = Depends(require_permission("view_costs"))):
    """Mẫu AI làm sai — dùng cho few-shot và eval."""
    with tenant_session(p.tenant_id) as db:
        rows = db.query(Message).filter(
            Message.status.in_([MsgStatus.REJECTED, MsgStatus.SENT]),
            Message.final_content != Message.draft_content).all()
        return [{"ai_draft": m.draft_content, "human_version": m.final_content,
                 "reject_reason": m.reject_reason, "status": m.status.value}
                for m in rows]
```

`backend/app/services/sender.py`:

```python
"""Gửi tin nhắn — có idempotency, có chế độ sandbox."""
from __future__ import annotations

import os

from leanai_core.logging import log_event

from ..db import tenant_session
from ..models import Message, MsgStatus

SANDBOX = os.getenv("SEND_SANDBOX", "true").lower() == "true"


def send_via_channel(*, channel: str, customer_id: int, content: str,
                     idempotency_key: str, tenant_id: str) -> dict:
    # 1. chống gửi trùng
    with tenant_session(tenant_id) as db:
        existing = db.query(Message).filter(
            Message.idempotency_key == idempotency_key,
            Message.status == MsgStatus.SENT).first()
        if existing:
            log_event("send_duplicate_blocked", tenant=tenant_id,
                      customer=customer_id, key=idempotency_key)
            return {"status": "sent", "duplicate": True,
                    "note": "đã gửi trước đó, không gửi lại"}

    # 2. gửi thật (hoặc sandbox)
    if SANDBOX:
        log_event("send_sandbox", tenant=tenant_id, customer=customer_id,
                  channel=channel, length=len(content))
        return {"status": "sent", "sandbox": True, "channel": channel}

    try:
        if channel == "zalo":
            result = _send_zalo(customer_id, content)
        else:
            result = _send_sms(customer_id, content)
        log_event("send_ok", tenant=tenant_id, customer=customer_id, channel=channel)
        return {"status": "sent", **result}
    except Exception as e:
        log_event("send_failed", tenant=tenant_id, customer=customer_id,
                  error=f"{type(e).__name__}: {e}")
        return {"status": "failed", "error": str(e)}


def _send_zalo(customer_id: int, content: str) -> dict:
    raise NotImplementedError("Tích hợp Zalo OA API ở đây")


def _send_sms(customer_id: int, content: str) -> dict:
    raise NotImplementedError("Tích hợp nhà cung cấp SMS ở đây")
```

---

## 3. Việc phải làm

1. **Bật `SEND_SANDBOX=true`** — không gửi tin thật trong giai đoạn học.
2. Duyệt 30 tin: approve 20, edit 7, reject 3.
3. Bấm Approve **hai lần liên tiếp** trên cùng tin → xác nhận chỉ gửi một lần.
4. Thay đổi dữ liệu khách (đặt `has_open_complaint=True`) rồi bấm Approve → guardrail phải chặn.
5. Gọi `/learning-samples` → phải thu được 10 mẫu AI làm sai.

---

## 4. PASS/FAIL

- [ ] Approve / Edit / Reject đều hoạt động
- [ ] Reject **bắt buộc** nhập lý do
- [ ] Guardrail chạy lại tại thời điểm gửi và chặn được
- [ ] Bấm Approve 2 lần chỉ gửi 1 tin
- [ ] Danh sách sắp xếp theo rủi ro rồi giá trị
- [ ] Mọi hành động ghi vào `audit_logs`
- [ ] Thu được ≥ 10 mẫu học từ edit/reject
- [ ] Sandbox mode hoạt động, không gửi tin thật

---

## 5. Quiz + commit

```powershell
python quiz\quiz.py --day 87 ; python quiz\quiz.py --review
git add . ; git commit -m "day 87: human approval + send flow"
```
