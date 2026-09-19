# NGÀY 79 — Auth

> Phase 6 · 20' lý thuyết — 100' code

## 🎯 Mục tiêu

Đăng nhập, phiên, phân quyền theo vai trò — và **mọi request đều mang tenant context**.

---

## 1. Lý thuyết (20 phút)

### 1.1 Nguyên tắc

```
1. Mật khẩu: bcrypt/argon2, KHÔNG BAO GIỜ lưu thô
2. Session: cookie HttpOnly + SameSite, hoặc JWT ngắn hạn
3. tenant_id lấy từ SESSION, KHÔNG BAO GIỜ từ tham số request
4. Mọi endpoint mặc định yêu cầu đăng nhập (opt-out, không opt-in)
5. Phân quyền kiểm tra ở tầng service, không chỉ ở UI
```

> Điểm 3 là quan trọng nhất. Nếu client gửi `?tenant_id=clinic_002` và server tin, bạn vừa tạo lỗ hổng nghiêm trọng nhất có thể.

### 1.2 Ma trận quyền

| Quyền | Lễ tân | Quản lý | Chủ |
|---|---|---|---|
| Xem khách hàng | ✅ | ✅ | ✅ |
| Xem cơ hội | ✅ | ✅ | ✅ |
| Soạn tin nhắn | ✅ | ✅ | ✅ |
| **Duyệt tin nhắn** | ❌ | ✅ | ✅ |
| Xem chi phí AI | ❌ | ✅ | ✅ |
| Quản lý người dùng | ❌ | ❌ | ✅ |
| Import dữ liệu | ❌ | ✅ | ✅ |

---

## 2. Code (100 phút)

`backend/app/deps.py`:

```python
"""Auth, tenant context, phân quyền."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from fastapi import Cookie, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .db import get_session
from .models import Role, User

pwd = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
SESSION_TTL = timedelta(hours=12)

# Trong production dùng Redis; SQLite/dict chỉ cho giai đoạn dev
_sessions: dict[str, dict] = {}

PERMISSIONS: dict[Role, set[str]] = {
    Role.RECEPTIONIST: {"read_customers", "read_opportunities", "draft_message"},
    Role.MANAGER: {"read_customers", "read_opportunities", "draft_message",
                   "approve_message", "view_costs", "import_data"},
    Role.OWNER: {"read_customers", "read_opportunities", "draft_message",
                 "approve_message", "view_costs", "import_data", "manage_users"},
}


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    return pwd.verify(p, h)


def create_session(user: User) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"user_id": user.id, "tenant_id": user.tenant_id,
                        "role": user.role,
                        "expires": datetime.now(timezone.utc) + SESSION_TTL}
    return token


@dataclass_ctx := None  # placeholder tránh lỗi import ở ví dụ rút gọn


class Principal:
    """Danh tính của request hiện tại. tenant_id LUÔN từ session."""
    def __init__(self, user_id: int, tenant_id: str, role: Role):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role

    def can(self, permission: str) -> bool:
        return permission in PERMISSIONS.get(self.role, set())

    def require(self, permission: str) -> None:
        if not self.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Vai trò {self.role.value} không có quyền '{permission}'")


def current_principal(session_token: str | None = Cookie(default=None)) -> Principal:
    if not session_token or session_token not in _sessions:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Chưa đăng nhập")
    s = _sessions[session_token]
    if s["expires"] < datetime.now(timezone.utc):
        _sessions.pop(session_token, None)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Phiên đã hết hạn")
    return Principal(s["user_id"], s["tenant_id"], s["role"])


def require_permission(permission: str):
    def dep(p: Principal = Depends(current_principal)) -> Principal:
        p.require(permission)
        return p
    return dep


def tenant_scoped(db: Session, principal: Principal):
    """Trả về session đã set tenant context cho RLS (Ngày 80)."""
    db.execute("SET LOCAL app.tenant_id = :t", {"t": principal.tenant_id})
    return db
```

`backend/app/routers/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import (Principal, create_session, current_principal,
                    hash_password, verify_password, _sessions)
from ..models import AuditLog, Role, User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    tenant_id: str
    email: EmailStr
    password: str


class MeOut(BaseModel):
    user_id: int
    tenant_id: str
    role: Role
    permissions: list[str]


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_session)):
    user = db.query(User).filter(User.tenant_id == body.tenant_id,
                                 User.email == body.email,
                                 User.active.is_(True)).first()
    # so sánh mật khẩu kể cả khi không tìm thấy user -> chống dò tài khoản qua thời gian
    ok = verify_password(body.password, user.password_hash if user else
                         "$argon2id$v=19$m=65536,t=3,p=4$invalid")
    if not user or not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email hoặc mật khẩu không đúng")

    token = create_session(user)
    response.set_cookie("session_token", token, httponly=True, samesite="lax",
                        secure=True, max_age=12 * 3600)
    db.add(AuditLog(tenant_id=user.tenant_id, user_id=user.id,
                    action="login", entity="user", entity_id=str(user.id)))
    db.commit()
    return {"status": "ok", "role": user.role.value}


@router.post("/logout")
def logout(response: Response, session_token: str | None = None):
    _sessions.pop(session_token or "", None)
    response.delete_cookie("session_token")
    return {"status": "ok"}


@router.get("/me", response_model=MeOut)
def me(p: Principal = Depends(current_principal)):
    from ..deps import PERMISSIONS
    return MeOut(user_id=p.user_id, tenant_id=p.tenant_id, role=p.role,
                 permissions=sorted(PERMISSIONS.get(p.role, set())))
```

### Test bắt buộc

`backend/tests/test_auth.py`:

```python
def test_khong_dang_nhap_bi_chan(client):
    assert client.get("/customers").status_code == 401


def test_khong_the_gia_mao_tenant(client, login_clinic1):
    """Gửi tenant_id khác trong query KHÔNG được có tác dụng."""
    r = client.get("/customers?tenant_id=clinic_002")
    assert r.status_code == 200
    assert all(c["tenant_id"] == "clinic_001" for c in r.json())


def test_le_tan_khong_duyet_duoc(client, login_receptionist):
    assert client.post("/messages/1/approve").status_code == 403


def test_phien_het_han(client, expired_session):
    assert client.get("/auth/me").status_code == 401
```

---

## 3. PASS/FAIL

- [ ] Đăng nhập/đăng xuất hoạt động, cookie HttpOnly
- [ ] `tenant_id` **chỉ** lấy từ session, thử giả mạo qua query không có tác dụng
- [ ] Phân quyền chặn đúng: lễ tân không duyệt được tin
- [ ] Mật khẩu hash bằng argon2/bcrypt
- [ ] Đăng nhập được ghi vào `audit_logs`
- [ ] 4 test trên đều pass

---

## 4. Quiz + commit

```powershell
python quiz\quiz.py --day 79 ; python quiz\quiz.py --review
git add . ; git commit -m "day 79: auth + RBAC"
```
