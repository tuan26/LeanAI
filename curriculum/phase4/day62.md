# NGÀY 62 — Guardrails cho agent

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Chặn hành động nguy hiểm **bằng kiến trúc**, không bằng lời nhắc trong prompt.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Prompt không phải guardrail

```
❌ "Không được gửi quá 1 tin nhắn cho mỗi khách mỗi tuần"
   → model quên, hoặc bị injection ghi đè

✅ if last_sent_within_days(customer_id, 7): reject()
   → không thể vượt qua
```

Mọi ràng buộc quan trọng phải nằm trong **code chạy trước khi tool thực thi**.

### 1.2 Bốn tầng guardrail

```
1. TRƯỚC KHI GỌI TOOL : kiểm tra tham số, quyền, hạn mức
2. SAU KHI CÓ KẾT QUẢ : lọc dữ liệu nhạy cảm trước khi đưa về model
3. TRƯỚC KHI HÀNH ĐỘNG: quy tắc nghiệp vụ (tần suất, giờ gửi, danh sách chặn)
4. SAU KHI XONG        : kiểm tra kết quả cuối, chặn nếu vi phạm
```

### 1.3 Guardrail nghiệp vụ cho CareDesk-AI

| Quy tắc | Vì sao |
|---|---|
| Tối đa 1 tin/khách/7 ngày | tránh làm phiền |
| Không gửi trước 8h và sau 20h | phép lịch sự cơ bản |
| Không gửi cho khách trong danh sách chặn | khách đã yêu cầu ngừng liên hệ |
| Không gửi cho khách có khiếu nại chưa xử lý | đổ dầu vào lửa |
| Tin nhắn không chứa số không có trong DB | chống bịa (Ngày 13) |
| Tối đa 200 tin/ngày/phòng khám | chặn sự cố hàng loạt |
| Tổng giá trị hành động > X → cần quyền cao hơn | kiểm soát rủi ro |

> Quy tắc cuối cùng quan trọng: **hạn mức tổng**. Nếu có lỗi logic, nó giới hạn thiệt hại ở 200 tin thay vì 3.000 tin.

### 1.4 Fail closed, không fail open

Khi guardrail không kiểm tra được (DB lỗi, thiếu dữ liệu) → **chặn**, không cho qua. An toàn hơn là đúng.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| OWASP Top 10 for LLM | https://owasp.org/www-project-top-10-for-large-language-model-applications/ |
| Anthropic — Strengthen guardrails | https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails |

---

## 3. Thực hành (80 phút)

`leanai_core/guardrails.py`:

```python
"""Guardrail thực thi bằng code, chạy trước mọi hành động."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Callable


@dataclass
class GuardResult:
    allowed: bool
    rule: str = ""
    reason: str = ""
    severity: str = "block"        # block | warn


@dataclass
class GuardContext:
    tenant_id: str
    customer: dict = field(default_factory=dict)
    action: str = ""
    args: dict = field(default_factory=dict)
    now: datetime = field(default_factory=datetime.now)
    sent_history: list[dict] = field(default_factory=list)   # [{customer_id, at}]
    blocklist: set[str] = field(default_factory=set)
    daily_count: int = 0


class GuardrailEngine:
    def __init__(self):
        self.rules: list[tuple[str, Callable[[GuardContext], GuardResult]]] = []

    def rule(self, name: str):
        def deco(fn):
            self.rules.append((name, fn))
            return fn
        return deco

    def check(self, ctx: GuardContext) -> list[GuardResult]:
        out = []
        for name, fn in self.rules:
            try:
                r = fn(ctx)
            except Exception as e:
                # fail closed
                r = GuardResult(False, name, f"guardrail lỗi: {e} — chặn để an toàn")
            if not r.allowed:
                r.rule = r.rule or name
                out.append(r)
        return out

    def allow(self, ctx: GuardContext) -> tuple[bool, list[GuardResult]]:
        issues = self.check(ctx)
        blocking = [i for i in issues if i.severity == "block"]
        return (not blocking), issues


guards = GuardrailEngine()


@guards.rule("tần_suất")
def max_one_per_week(ctx: GuardContext) -> GuardResult:
    if ctx.action != "send_message":
        return GuardResult(True)
    cid = ctx.args.get("customer_id", "")
    recent = [h for h in ctx.sent_history
              if h["customer_id"] == cid
              and ctx.now - h["at"] < timedelta(days=7)]
    if recent:
        return GuardResult(False, reason=f"đã gửi cho {cid} cách đây "
                                         f"{(ctx.now - recent[-1]['at']).days} ngày")
    return GuardResult(True)


@guards.rule("giờ_gửi")
def business_hours(ctx: GuardContext) -> GuardResult:
    if ctx.action != "send_message":
        return GuardResult(True)
    if not (time(8, 0) <= ctx.now.time() <= time(20, 0)):
        return GuardResult(False, reason=f"ngoài giờ cho phép ({ctx.now:%H:%M}), "
                                         "chỉ gửi 08:00-20:00")
    return GuardResult(True)


@guards.rule("danh_sách_chặn")
def blocklist(ctx: GuardContext) -> GuardResult:
    cid = ctx.args.get("customer_id", "")
    if cid in ctx.blocklist:
        return GuardResult(False, reason=f"{cid} đã yêu cầu ngừng nhận tin")
    return GuardResult(True)


@guards.rule("khiếu_nại_chưa_xử_lý")
def open_complaint(ctx: GuardContext) -> GuardResult:
    if ctx.customer.get("khieu_nai_mo"):
        return GuardResult(False, reason="khách có khiếu nại chưa xử lý — "
                                         "chuyển cho quản lý thay vì gửi tin tự động")
    return GuardResult(True)


@guards.rule("số_liệu_ma")
def no_ghost_numbers(ctx: GuardContext) -> GuardResult:
    if ctx.action != "send_message":
        return GuardResult(True)
    msg = ctx.args.get("message", "")
    src = " ".join(str(v) for v in ctx.customer.values())

    def nums(t): return {re.sub(r"[.,\s]", "", x) for x in re.findall(r"\d[\d.,\s]*\d|\d", t)}
    ghost = nums(msg) - nums(src)
    ghost = {g for g in ghost if len(g) > 1}          # bỏ số lẻ vô hại
    if ghost:
        return GuardResult(False, reason=f"tin nhắn chứa số không có trong dữ liệu: {sorted(ghost)}")
    return GuardResult(True)


@guards.rule("từ_cấm")
def forbidden_words(ctx: GuardContext) -> GuardResult:
    msg = ctx.args.get("message", "").lower()
    hits = [w for w in ("khuyến mãi", "giảm giá", "miễn phí", "tặng", "cam kết 100%")
            if w in msg]
    if hits:
        return GuardResult(False, reason=f"hứa hẹn không được phép: {hits}")
    return GuardResult(True)


@guards.rule("hạn_mức_ngày")
def daily_cap(ctx: GuardContext, cap: int = 200) -> GuardResult:
    if ctx.action == "send_message" and ctx.daily_count >= cap:
        return GuardResult(False, reason=f"đã đạt hạn mức {cap} tin/ngày cho tenant này")
    return GuardResult(True)
```

`exercises/day62/guard_test.py`:

```python
from datetime import datetime, timedelta
from leanai_core.guardrails import guards, GuardContext

BASE = datetime(2026, 9, 19, 10, 0)
CUST = {"ten": "Nguyễn Thị Lan", "buoi_con_lai": 4, "gia_tri_chua_dung": 4800000,
        "khieu_nai_mo": False}

CASES = [
 ("hợp lệ", GuardContext(tenant_id="c1", customer=CUST, action="send_message",
   args={"customer_id": "C001", "message": "Chị Lan ơi, gói còn 4 buổi ạ."}, now=BASE)),
 ("gửi lại trong 7 ngày", GuardContext(tenant_id="c1", customer=CUST, action="send_message",
   args={"customer_id": "C001", "message": "Chị Lan ơi, gói còn 4 buổi ạ."}, now=BASE,
   sent_history=[{"customer_id": "C001", "at": BASE - timedelta(days=2)}])),
 ("gửi lúc 23h", GuardContext(tenant_id="c1", customer=CUST, action="send_message",
   args={"customer_id": "C001", "message": "Chị Lan ơi, gói còn 4 buổi ạ."},
   now=BASE.replace(hour=23))),
 ("khách chặn", GuardContext(tenant_id="c1", customer=CUST, action="send_message",
   args={"customer_id": "C001", "message": "Xin chào"}, now=BASE, blocklist={"C001"})),
 ("số bịa", GuardContext(tenant_id="c1", customer=CUST, action="send_message",
   args={"customer_id": "C001", "message": "Chị còn 7 buổi, giảm 30% ạ"}, now=BASE)),
 ("khiếu nại mở", GuardContext(tenant_id="c1", customer={**CUST, "khieu_nai_mo": True},
   action="send_message", args={"customer_id": "C001", "message": "Chị Lan ơi"}, now=BASE)),
 ("vượt hạn mức", GuardContext(tenant_id="c1", customer=CUST, action="send_message",
   args={"customer_id": "C001", "message": "Chị Lan ơi, gói còn 4 buổi ạ."},
   now=BASE, daily_count=200)),
]

for name, ctx in CASES:
    ok, issues = guards.allow(ctx)
    print(f"\n{'✓ CHO PHÉP' if ok else '🚫 CHẶN'}  {name}")
    for i in issues:
        print(f"    [{i.rule}] {i.reason}")
```

---

## 4. Bài tập

**Bài 1 — Tích hợp vào Agent.** Chạy `guards.allow()` **trước** mọi `registry.execute` của tool ghi. Nếu bị chặn, trả lý do về cho model để nó tìm cách khác (ví dụ: đề xuất chuyển cho người).

**Bài 2 — Test xuyên thủng.** Thử 10 cách khiến agent gửi tin vi phạm (qua prompt injection, qua yêu cầu trực tiếp của người dùng, qua nhiều bước vòng vo). Bao nhiêu cách vượt được? Cách nào vượt → vá bằng **code**, không bằng prompt.

**Bài 3 — Fail closed.** Mô phỏng DB lịch sử gửi tin bị lỗi. Hệ thống có chặn không (đúng) hay cho qua (sai)? Sửa cho đúng.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 62 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] ≥ 7 guardrail chạy bằng code trước mọi hành động ghi
- [ ] Không có cách nào (kể cả injection) vượt qua guardrail
- [ ] Guardrail lỗi → **chặn** (fail closed)
- [ ] Agent nhận được lý do bị chặn và tìm hướng khác
- [ ] Có hạn mức tổng giới hạn thiệt hại khi lỗi hàng loạt
- [ ] Quiz ≥ 80%
