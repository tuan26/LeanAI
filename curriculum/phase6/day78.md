# NGÀY 78 — Data model

> Phase 6 · 30' thiết kế — 90' code migration + seed

## 🎯 Mục tiêu

Schema database đầy đủ, có migration chạy được, có dữ liệu mẫu 2 phòng khám × 200 khách.

---

## 1. Thiết kế (30 phút)

### Nguyên tắc

```
1. MỌI bảng nghiệp vụ có tenant_id NOT NULL
2. Index (tenant_id, <cột hay lọc>) cho mọi bảng
3. Không xoá cứng — dùng status/deleted_at (audit)
4. Tiền lưu dạng số nguyên VNĐ, không dùng float
5. Ngày giờ lưu UTC, hiển thị theo giờ VN
```

### Sơ đồ

```
tenants ──┬── users
          ├── customers ──┬── packages ── package_sessions
          │               └── opportunities ── messages
          ├── documents (RAG, Ngày 81)
          └── audit_logs
```

---

## 2. Code (90 phút)

`backend/app/models.py`:

```python
"""Schema CareDesk-AI."""
from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, Enum, ForeignKey,
                        Index, Integer, String, Text, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TenantMixin:
    tenant_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)


# ---------- enums ----------
class Role(str, PyEnum):
    RECEPTIONIST = "receptionist"; MANAGER = "manager"; OWNER = "owner"


class OppType(str, PyEnum):
    OVERDUE_REVISIT = "overdue_revisit"
    UNUSED_PACKAGE = "unused_package"
    EXPIRING_SOON = "expiring_soon"
    LOST_BOOKING = "lost_booking"
    HIGH_INTENT_LEAD = "high_intent_lead"


class OppStatus(str, PyEnum):
    NEW = "new"; DRAFTED = "drafted"; PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"; SENT = "sent"; REJECTED = "rejected"
    CONVERTED = "converted"; EXPIRED = "expired"


class MsgStatus(str, PyEnum):
    DRAFT = "draft"; PENDING = "pending"; APPROVED = "approved"
    EDITED = "edited"; REJECTED = "rejected"; SENT = "sent"; FAILED = "failed"


# ---------- bảng ----------
class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    branch: Mapped[str] = mapped_column(String(50), default="")
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Ho_Chi_Minh")
    daily_message_cap: Mapped[int] = mapped_column(Integer, default=200)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base, TenantMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.RECEPTIONIST)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_email"),)


class Customer(Base, TenantMixin):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(60), default="")
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(30), default="")
    zalo_id: Mapped[str] = mapped_column(String(60), default="")
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_visit: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_visit: Mapped[date | None] = mapped_column(Date, nullable=True)
    lifetime_value: Mapped[int] = mapped_column(BigInteger, default=0)   # VNĐ
    notes: Mapped[str] = mapped_column(Text, default="")
    opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    has_open_complaint: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_channel: Mapped[str] = mapped_column(String(20), default="zalo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    packages: Mapped[list["Package"]] = relationship(back_populates="customer")
    __table_args__ = (
        Index("ix_cust_tenant_lastvisit", "tenant_id", "last_visit"),
        Index("ix_cust_tenant_phone", "tenant_id", "phone"),
    )


class Package(Base, TenantMixin):
    __tablename__ = "packages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(200))
    total_sessions: Mapped[int] = mapped_column(Integer)
    used_sessions: Mapped[int] = mapped_column(Integer, default=0)
    price_vnd: Mapped[int] = mapped_column(BigInteger)
    purchased_at: Mapped[date] = mapped_column(Date)
    expires_at: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    customer: Mapped[Customer] = relationship(back_populates="packages")

    @property
    def remaining(self) -> int:
        return max(self.total_sessions - self.used_sessions, 0)

    @property
    def unused_value(self) -> int:
        if not self.total_sessions:
            return 0
        return round(self.price_vnd * self.remaining / self.total_sessions)

    __table_args__ = (Index("ix_pkg_tenant_expires", "tenant_id", "expires_at"),)


class Opportunity(Base, TenantMixin):
    __tablename__ = "opportunities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("packages.id"), nullable=True)
    opp_type: Mapped[OppType] = mapped_column(Enum(OppType))
    status: Mapped[OppStatus] = mapped_column(Enum(OppStatus), default=OppStatus.NEW)
    estimated_value_vnd: Mapped[int] = mapped_column(BigInteger, default=0)
    confidence: Mapped[float] = mapped_column(Integer, default=0)   # 0-100
    reason_data: Mapped[str] = mapped_column(Text, default="{}")    # JSON số liệu gốc
    explanation: Mapped[str] = mapped_column(Text, default="")      # LLM sinh
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    converted_value_vnd: Mapped[int] = mapped_column(BigInteger, default=0)

    __table_args__ = (
        Index("ix_opp_tenant_status", "tenant_id", "status"),
        UniqueConstraint("tenant_id", "customer_id", "opp_type", "detected_at",
                         name="uq_opp_dedup"),
    )


class Message(Base, TenantMixin):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(ForeignKey("opportunities.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="zalo")
    draft_content: Mapped[str] = mapped_column(Text)
    final_content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[MsgStatus] = mapped_column(Enum(MsgStatus), default=MsgStatus.DRAFT)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reject_reason: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_msg_tenant_status", "tenant_id", "status"),
        Index("ix_msg_cust_sent", "tenant_id", "customer_id", "sent_at"),
        UniqueConstraint("idempotency_key", name="uq_msg_idem"),
    )


class AuditLog(Base, TenantMixin):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(60), default="")
    detail: Mapped[str] = mapped_column(Text, default="{}")
    trace_id: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index("ix_audit_tenant_time", "tenant_id", "created_at"),)
```

### Seed dữ liệu

`backend/scripts/seed.py` — sinh 2 tenant × 200 khách với phân bố thực tế:

```python
"""Sinh dữ liệu mẫu có phân bố giống thật."""
import random
from datetime import date, timedelta

random.seed(42)
TODAY = date(2026, 9, 19)
SERVICES = [("Trị liệu da mặt", 10, 12_000_000), ("Massage trị liệu", 20, 8_000_000),
            ("Chăm sóc da cơ bản", 8, 6_000_000), ("Triệt lông", 12, 15_000_000)]

def make_customer(tenant: str, i: int) -> dict:
    # phân bố: 60% đang hoạt động, 25% chậm quay lại, 15% đã rời bỏ
    r = random.random()
    days_since = int(random.gauss(20, 10)) if r < 0.6 else \
                 int(random.gauss(110, 30)) if r < 0.85 else int(random.gauss(250, 60))
    days_since = max(1, days_since)
    svc, total, price = random.choice(SERVICES)
    used = random.choice([total, total, random.randint(0, total - 1)])
    purchased = TODAY - timedelta(days=random.randint(30, 400))
    return {
        "tenant_id": tenant, "external_id": f"{tenant}-{i:04d}",
        "full_name": f"Khách {i}", "phone": f"09{random.randint(10**8, 10**9-1)}",
        "last_visit": TODAY - timedelta(days=days_since),
        "lifetime_value": random.randint(3, 60) * 1_000_000,
        "opt_out": random.random() < 0.03,
        "has_open_complaint": random.random() < 0.05,
        "notes": random.choice(["", "", "", "phàn nàn chờ lâu", "thích khung giờ sáng",
                                "không thích gọi điện"]),
        "package": {"service_name": svc, "total_sessions": total, "used_sessions": used,
                    "price_vnd": price, "purchased_at": purchased,
                    "expires_at": purchased + timedelta(days=180)},
    }
```

---

## 3. PASS/FAIL

- [ ] Mọi bảng nghiệp vụ có `tenant_id NOT NULL` + index
- [ ] Migration chạy được (`alembic upgrade head`)
- [ ] Seed 2 tenant × 200 khách với phân bố thực tế (không phải toàn ca đẹp)
- [ ] Tiền lưu số nguyên VNĐ
- [ ] Có `audit_logs` ghi được mọi hành động
- [ ] `idempotency_key` unique trên bảng messages

---

## 4. Quiz + commit

```powershell
python quiz\quiz.py --day 78 ; python quiz\quiz.py --review
git add . ; git commit -m "day 78: data model + migration + seed"
```
