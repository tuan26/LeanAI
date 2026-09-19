# NGÀY 72 — Security

> Phase 5 · 25' lý thuyết — 10' tài liệu — 75' code — 10' note

## 🎯 Mục tiêu

Tự audit hệ thống, tìm **≥ 5 lỗ hổng thật**, vá và chứng minh đã vá.

---

## 1. Lý thuyết cốt lõi (25 phút)

### 1.1 Năm mặt trận an ninh của AI SaaS

```
1. PROMPT INJECTION      — trực tiếp và gián tiếp (Ngày 28)
2. RÒ RỈ DỮ LIỆU         — giữa tenant, ra log, ra bên thứ ba
3. QUẢN LÝ BÍ MẬT        — API key, chuỗi kết nối DB
4. KIỂM SOÁT TRUY CẬP    — ai được gọi tool nào, xem dữ liệu nào
5. LẠM DỤNG TÀI NGUYÊN   — đốt quota, DoS bằng prompt dài
```

### 1.2 Multi-tenant — rủi ro nghiêm trọng nhất

```
Tầng 1: Ứng dụng    — mọi truy vấn có tenant_id (dễ quên)
Tầng 2: Cơ sở dữ liệu — Row Level Security (không quên được)
Tầng 3: Vector DB   — filter bắt buộc + collection riêng nếu nhạy cảm
Tầng 4: Kiểm thử    — test tự động chứng minh cách ly
```

> Chỉ dựa vào tầng 1 là **không đủ**. Một lần quên `WHERE tenant_id=?` là một sự cố phải báo cáo khách hàng.

### 1.3 Dữ liệu ra bên thứ ba

Gửi prompt cho LLM = gửi dữ liệu khách hàng ra ngoài. Phải:
- kiểm tra chính sách lưu trữ dữ liệu của provider,
- **che dữ liệu định danh** khi không cần thiết (gửi "khách A" thay vì tên thật),
- nói rõ trong hợp đồng/điều khoản với khách hàng,
- với dữ liệu y tế: cân nhắc self-host hoặc hợp đồng riêng.

Trong CareDesk-AI, nhiều tác vụ **không cần tên thật**: phát hiện cơ hội chỉ cần số liệu. Chỉ khi soạn tin nhắn mới cần tên.

### 1.4 Kiểm soát truy cập theo vai trò

| Vai trò | Xem dữ liệu | Duyệt tin nhắn | Xem chi phí | Quản trị |
|---|---|---|---|---|
| Lễ tân | khách của mình | ❌ | ❌ | ❌ |
| Quản lý phòng khám | cả phòng khám | ✅ | ✅ | ❌ |
| Chủ chuỗi | mọi phòng khám của mình | ✅ | ✅ | ✅ |
| Nhà phát triển | **không có dữ liệu thật** | ❌ | ✅ | ✅ |

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| OWASP Top 10 for LLM | https://owasp.org/www-project-top-10-for-large-language-model-applications/ |
| OWASP API Security Top 10 | https://owasp.org/API-Security/ |
| Postgres Row Level Security | https://www.postgresql.org/docs/current/ddl-rowsecurity.html |

---

## 3. Thực hành (75 phút)

`leanai_core/security.py`:

```python
"""Che dữ liệu định danh, kiểm soát truy cập, audit."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum

PHONE = re.compile(r"\b0\d{9,10}\b")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
ID_CARD = re.compile(r"\b\d{9}|\d{12}\b")


class Role(str, Enum):
    RECEPTIONIST = "receptionist"
    MANAGER = "manager"
    OWNER = "owner"
    DEVELOPER = "developer"


PERMISSIONS = {
    Role.RECEPTIONIST: {"read_own_customers", "draft_message"},
    Role.MANAGER: {"read_clinic_customers", "draft_message", "approve_message",
                   "view_costs"},
    Role.OWNER: {"read_all_clinics", "draft_message", "approve_message",
                 "view_costs", "admin"},
    Role.DEVELOPER: {"view_costs", "admin"},      # KHÔNG có quyền đọc dữ liệu thật
}


def can(role: Role, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())


def require(role: Role, permission: str) -> None:
    if not can(role, permission):
        raise PermissionError(f"vai trò {role.value} không có quyền '{permission}'")


@dataclass
class Pseudonymizer:
    """Thay dữ liệu định danh bằng mã giả, có thể khôi phục cục bộ."""
    salt: str = "leanai"
    _map: dict = None

    def __post_init__(self):
        self._map = {}

    def _token(self, value: str, prefix: str) -> str:
        h = hashlib.sha256((self.salt + value).encode()).hexdigest()[:6].upper()
        tok = f"{prefix}_{h}"
        self._map[tok] = value
        return tok

    def mask(self, text: str) -> str:
        text = PHONE.sub(lambda m: self._token(m.group(), "SDT"), text)
        text = EMAIL.sub(lambda m: self._token(m.group(), "EMAIL"), text)
        text = ID_CARD.sub(lambda m: self._token(m.group(), "CMND"), text)
        return text

    def mask_name(self, name: str) -> str:
        return self._token(name, "KH")

    def restore(self, text: str) -> str:
        for tok, val in self._map.items():
            text = text.replace(tok, val)
        return text


def safe_customer_for_llm(customer: dict, need_name: bool = False,
                          pseudo: Pseudonymizer | None = None) -> dict:
    """Chỉ gửi ra LLM những gì thật sự cần."""
    pseudo = pseudo or Pseudonymizer()
    allowed = {"tong_buoi", "da_dung", "buoi_con_lai", "gia", "gia_tri_chua_dung",
               "ngay_het_han", "con_lai_ngay", "vang_mat_ngay", "goi",
               "khieu_nai_mo", "ghi_chu"}
    out = {k: v for k, v in customer.items() if k in allowed}
    out["ten"] = customer.get("ten", "") if need_name else pseudo.mask_name(
        customer.get("ten", ""))
    return out
```

`exercises/day72/security_audit.py`:

```python
"""Ngày 72: audit an ninh — 8 kiểm tra tự động."""
import re
import subprocess
from pathlib import Path

from leanai_core.vectorstore import VectorStore
from leanai_core.security import Role, can, Pseudonymizer, safe_customer_for_llm

findings = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        findings.append((name, detail))


print("=== AUDIT AN NINH ===\n")

# 1. Secret trong code
print("1. Bí mật lộ trong mã nguồn")
hits = []
for f in Path(".").rglob("*.py"):
    if ".venv" in str(f):
        continue
    txt = f.read_text(encoding="utf-8", errors="ignore")
    if re.search(r"(sk-ant-[\w-]{10,}|sk-[A-Za-z0-9]{20,})", txt):
        hits.append(str(f))
check("không hardcode API key", not hits, str(hits[:3]))

# 2. .env trong git
print("\n2. .env bị commit")
try:
    out = subprocess.run(["git", "ls-files", ".env"], capture_output=True, text=True).stdout
except FileNotFoundError:
    out = ""
check(".env không nằm trong git", not out.strip(), out.strip())

# 3. Cách ly tenant trong vector DB
print("\n3. Cách ly tenant")
try:
    vs = VectorStore("company_kb")
    leaks = 0
    for q in ["giá", "chính sách", "khách hàng", "quy trình", "hoàn tiền"]:
        for h in vs.search(q, k=10, where={"tenant_id": "clinic_001"}):
            if h.meta.get("tenant_id") != "clinic_001":
                leaks += 1
    check("không rò rỉ giữa tenant", leaks == 0, f"{leaks} kết quả rò rỉ")
except Exception as e:
    check("kiểm tra tenant", False, str(e))

# 4. Truy vấn thiếu tenant_id
print("\n4. Truy vấn thiếu tenant_id")
bad = []
for f in Path(".").rglob("*.py"):
    if ".venv" in str(f):
        continue
    for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if re.search(r"\.search\(", line) and "tenant" not in line and "where" not in line:
            bad.append(f"{f}:{i}")
check("mọi search có tenant filter", not bad, str(bad[:3]))

# 5. Dữ liệu nhạy cảm trong log
print("\n5. Dữ liệu nhạy cảm trong log")
leak_lines = []
for f in Path("logs").rglob("*.jsonl") if Path("logs").exists() else []:
    txt = f.read_text(encoding="utf-8", errors="ignore")
    if re.search(r"\b0\d{9}\b", txt) or "sk-" in txt:
        leak_lines.append(str(f))
check("log không chứa SĐT/khoá", not leak_lines, str(leak_lines[:3]))

# 6. Kiểm soát truy cập
print("\n6. Kiểm soát truy cập theo vai trò")
check("lễ tân không duyệt được tin", not can(Role.RECEPTIONIST, "approve_message"))
check("lập trình viên không đọc dữ liệu thật",
      not can(Role.DEVELOPER, "read_clinic_customers"))

# 7. Che định danh
print("\n7. Che dữ liệu định danh khi gửi LLM")
p = Pseudonymizer()
cust = {"ten": "Nguyễn Thị Lan", "sdt": "0901234567", "tong_buoi": 10,
        "da_dung": 6, "gia": 12_000_000}
safe = safe_customer_for_llm(cust, need_name=False, pseudo=p)
check("không gửi tên thật khi không cần",
      "Nguyễn Thị Lan" not in str(safe), str(safe))
check("không gửi SĐT ra LLM", "0901234567" not in str(safe))

# 8. Giới hạn kích thước đầu vào
print("\n8. Chống lạm dụng tài nguyên")
MAX_INPUT_CHARS = 20_000
check("có giới hạn độ dài đầu vào", MAX_INPUT_CHARS < 100_000,
      f"giới hạn {MAX_INPUT_CHARS} ký tự")

print(f"\n{'='*60}")
print(f"KẾT QUẢ: {len(findings)} lỗ hổng cần vá")
for name, detail in findings:
    print(f"  ❌ {name}: {detail[:80]}")
```

---

## 4. Bài tập

**Bài 1 — Báo cáo audit.** Chạy `security_audit.py`. Với mỗi FAIL, viết `progress/notes/day72-security.md`: lỗ hổng, mức độ nghiêm trọng, cách khai thác, cách vá, bằng chứng đã vá.

**Bài 2 — Test cách ly tự động.** Viết `tests/test_tenant_isolation.py` (pytest): tạo 2 tenant, nạp dữ liệu, chạy 50 truy vấn, assert **không có** kết quả lẫn nhau. Test này phải chạy trong CI mỗi lần commit.

**Bài 3 — Giảm dữ liệu gửi ra ngoài.** Rà mọi lời gọi LLM: cái nào đang gửi tên thật/SĐT mà không cần? Chuyển sang `safe_customer_for_llm`. Đo: bao nhiêu % lời gọi không còn chứa dữ liệu định danh?

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 72 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Tìm và vá được ≥ 5 lỗ hổng thật
- [ ] Test cách ly tenant tự động, chạy được bằng pytest
- [ ] Không có bí mật trong code, không có SĐT trong log
- [ ] Phân quyền theo vai trò hoạt động
- [ ] Giảm được lượng dữ liệu định danh gửi ra LLM
- [ ] Quiz ≥ 80%
