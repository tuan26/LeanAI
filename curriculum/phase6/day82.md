# NGÀY 82 — Revenue Opportunity engine

> Phase 6 · 20' thiết kế — 100' code
> ⭐ Đây là **trái tim nghiệp vụ** của sản phẩm. Và nó **không dùng LLM**.

## 🎯 Mục tiêu

Phát hiện 5 loại cơ hội doanh thu bằng **SQL + rule**, chính xác 100%, chạy trên 3.000 khách trong vài giây.

---

## 1. Thiết kế (20 phút)

### Năm loại cơ hội

| Loại | Điều kiện | Giá trị ước tính |
|---|---|---|
| `OVERDUE_REVISIT` | vắng > 90 ngày **và** còn buổi chưa dùng | giá trị buổi chưa dùng |
| `UNUSED_PACKAGE` | mua > 30 ngày, dùng < 20% số buổi | giá trị buổi chưa dùng |
| `EXPIRING_SOON` | còn buổi, hết hạn trong 30 ngày | giá trị buổi chưa dùng |
| `LOST_BOOKING` | có lịch hẹn nhưng không đến, > 14 ngày chưa đặt lại | giá trung bình 1 buổi |
| `HIGH_INTENT_LEAD` | hỏi giá/xem dịch vụ nhưng chưa mua trong 30 ngày | giá gói phổ biến nhất |

### Ba quy tắc loại trừ (áp dụng cho MỌI loại)

```
1. opt_out = true                          → bỏ qua
2. has_open_complaint = true               → bỏ qua, chuyển quản lý
3. đã gửi tin trong 7 ngày                 → bỏ qua
```

### Vì sao không dùng LLM

```
✓ Luật rõ ràng, xác định được
✓ Cần chính xác 100% (đây là tiền của khách hàng)
✓ Chạy trên 3.000 khách → LLM tốn 3.000 lần gọi
✓ Kiểm toán được: giải thích chính xác vì sao khách này được chọn
✓ Chi phí ~0, latency ~vài giây
```

Đây là ADR-002 của Ngày 77. Hôm nay bạn thực thi nó.

---

## 2. Code (100 phút)

`backend/app/services/detector.py`:

```python
"""Phát hiện cơ hội doanh thu — RULE, không LLM."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..models import Customer, Message, MsgStatus, OppType, Opportunity, Package


@dataclass
class DetectionRules:
    overdue_days: int = 90
    unused_after_days: int = 30
    unused_max_ratio: float = 0.2
    expiring_within_days: int = 30
    min_value_vnd: int = 500_000          # bỏ qua cơ hội quá nhỏ
    cooldown_days: int = 7                # không gửi lại trong N ngày


@dataclass
class DetectedOpportunity:
    customer_id: int
    opp_type: OppType
    estimated_value_vnd: int
    confidence: int                        # 0-100
    reason_data: dict = field(default_factory=dict)
    package_id: int | None = None
    expires_at: date | None = None


def _recently_contacted(db: Session, tenant_id: str, days: int) -> set[int]:
    cutoff = date.today() - timedelta(days=days)
    rows = db.query(Message.customer_id).filter(
        Message.tenant_id == tenant_id,
        Message.status == MsgStatus.SENT,
        Message.sent_at >= cutoff).distinct().all()
    return {r[0] for r in rows}


def _excluded(db: Session, tenant_id: str, rules: DetectionRules) -> set[int]:
    """Khách bị loại khỏi mọi loại cơ hội."""
    rows = db.query(Customer.id).filter(
        Customer.tenant_id == tenant_id,
        or_(Customer.opt_out.is_(True), Customer.has_open_complaint.is_(True))
    ).all()
    return {r[0] for r in rows} | _recently_contacted(db, tenant_id, rules.cooldown_days)


def detect_all(db: Session, tenant_id: str, today: date | None = None,
               rules: DetectionRules | None = None) -> list[DetectedOpportunity]:
    today = today or date.today()
    rules = rules or DetectionRules()
    skip = _excluded(db, tenant_id, rules)
    out: list[DetectedOpportunity] = []

    rows = (db.query(Customer, Package)
            .join(Package, Package.customer_id == Customer.id)
            .filter(Customer.tenant_id == tenant_id,
                    Package.active.is_(True))
            .all())

    for cust, pkg in rows:
        if cust.id in skip:
            continue
        remaining = pkg.total_sessions - pkg.used_sessions
        if remaining <= 0:
            continue
        value = pkg.unused_value
        if value < rules.min_value_vnd:
            continue

        days_absent = (today - cust.last_visit).days if cust.last_visit else 9999
        days_since_purchase = (today - pkg.purchased_at).days
        days_to_expiry = (pkg.expires_at - today).days
        used_ratio = pkg.used_sessions / pkg.total_sessions

        base = {"ten": cust.full_name, "goi": pkg.service_name,
                "tong_buoi": pkg.total_sessions, "da_dung": pkg.used_sessions,
                "buoi_con_lai": remaining, "gia_goi": pkg.price_vnd,
                "gia_tri_chua_dung": value, "vang_mat_ngay": days_absent,
                "ngay_het_han": pkg.expires_at.isoformat(),
                "con_lai_ngay": days_to_expiry,
                "ghi_chu": cust.notes, "lifetime_value": cust.lifetime_value}

        # --- 1. sắp hết hạn: ưu tiên cao nhất vì có deadline thật ---
        if 0 < days_to_expiry <= rules.expiring_within_days:
            conf = 90 if days_to_expiry <= 14 else 75
            out.append(DetectedOpportunity(
                cust.id, OppType.EXPIRING_SOON, value, conf,
                {**base, "trigger": f"hết hạn sau {days_to_expiry} ngày"},
                pkg.id, pkg.expires_at))
            continue

        # --- 2. quá hạn tái khám ---
        if days_absent >= rules.overdue_days:
            conf = min(60 + (days_absent - rules.overdue_days) // 10, 90)
            if days_absent > 300:
                conf -= 20                 # quá lâu → khả năng đã rời bỏ
            out.append(DetectedOpportunity(
                cust.id, OppType.OVERDUE_REVISIT, value, max(conf, 30),
                {**base, "trigger": f"vắng mặt {days_absent} ngày"},
                pkg.id, pkg.expires_at))
            continue

        # --- 3. gói mua lâu chưa dùng ---
        if days_since_purchase >= rules.unused_after_days and used_ratio <= rules.unused_max_ratio:
            out.append(DetectedOpportunity(
                cust.id, OppType.UNUSED_PACKAGE, value, 70,
                {**base, "trigger": f"mua {days_since_purchase} ngày trước, "
                                    f"mới dùng {pkg.used_sessions}/{pkg.total_sessions}"},
                pkg.id, pkg.expires_at))

    return sorted(out, key=lambda o: (-o.estimated_value_vnd, -o.confidence))


def persist(db: Session, tenant_id: str, found: list[DetectedOpportunity]) -> dict:
    """Lưu cơ hội, tránh trùng với cơ hội đang mở."""
    from ..models import OppStatus
    open_keys = {(o.customer_id, o.opp_type) for o in
                 db.query(Opportunity).filter(
                     Opportunity.tenant_id == tenant_id,
                     Opportunity.status.in_([OppStatus.NEW, OppStatus.DRAFTED,
                                             OppStatus.PENDING_APPROVAL,
                                             OppStatus.APPROVED])).all()}
    created = skipped = 0
    for o in found:
        if (o.customer_id, o.opp_type) in open_keys:
            skipped += 1
            continue
        db.add(Opportunity(
            tenant_id=tenant_id, customer_id=o.customer_id, package_id=o.package_id,
            opp_type=o.opp_type, estimated_value_vnd=o.estimated_value_vnd,
            confidence=o.confidence,
            reason_data=json.dumps(o.reason_data, ensure_ascii=False, default=str),
            expires_at=o.expires_at))
        created += 1
    db.commit()
    return {"phát hiện": len(found), "tạo mới": created, "bỏ qua (đã có)": skipped,
            "tổng giá trị": sum(o.estimated_value_vnd for o in found)}
```

### Test

`backend/tests/test_detector.py`:

```python
import pytest
from datetime import date, timedelta
from app.services.detector import detect_all, DetectionRules
from app.models import OppType

TODAY = date(2026, 9, 19)


def test_khach_qua_han_duoc_phat_hien(db_with_overdue_customer):
    found = detect_all(db_with_overdue_customer, "clinic_001", TODAY)
    assert any(o.opp_type == OppType.OVERDUE_REVISIT for o in found)


def test_khach_opt_out_bi_loai(db_with_optout_customer):
    found = detect_all(db_with_optout_customer, "clinic_001", TODAY)
    assert not found


def test_khach_khieu_nai_bi_loai(db_with_complaint):
    assert not detect_all(db_with_complaint, "clinic_001", TODAY)


def test_vua_gui_tin_khong_gui_lai(db_with_recent_message):
    assert not detect_all(db_with_recent_message, "clinic_001", TODAY)


def test_gia_tri_tinh_dung(db_with_overdue_customer):
    o = detect_all(db_with_overdue_customer, "clinic_001", TODAY)[0]
    # gói 12.000.000đ, 10 buổi, dùng 6 -> còn 4 -> 4.800.000đ
    assert o.estimated_value_vnd == 4_800_000


def test_sap_het_han_uu_tien_hon(db_with_expiring):
    found = detect_all(db_with_expiring, "clinic_001", TODAY)
    assert found[0].opp_type == OppType.EXPIRING_SOON


def test_khong_tao_trung_co_hoi_dang_mo(db_with_open_opportunity):
    from app.services.detector import persist
    found = detect_all(db_with_open_opportunity, "clinic_001", TODAY)
    r = persist(db_with_open_opportunity, "clinic_001", found)
    assert r["tạo mới"] == 0
```

---

## 3. PASS/FAIL

- [ ] Phát hiện đủ ≥ 3 loại cơ hội trên dữ liệu seed
- [ ] **Không dùng LLM** trong toàn bộ detector
- [ ] Ba quy tắc loại trừ hoạt động (test chứng minh)
- [ ] Giá trị ước tính tính đúng đến từng đồng
- [ ] Không tạo trùng cơ hội đang mở
- [ ] Chạy trên 3.000 khách < 5 giây
- [ ] 7 test pass

---

## 4. Quiz + commit

```powershell
pytest backend/tests/test_detector.py -v
python quiz\quiz.py --day 82 ; python quiz\quiz.py --review
git add . ; git commit -m "day 82: revenue opportunity detector (rule-based)"
```
