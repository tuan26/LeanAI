# NGÀY 20 — Error handling & retry

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Client chịu được lỗi thật: 429, 500, timeout, output cắt, JSON hỏng. Sản phẩm production **sẽ** gặp tất cả những thứ này.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Phân loại lỗi — quyết định retry hay không

| Loại | Ví dụ | Retry? | Xử lý |
|---|---|---|---|
| **Lỗi do bạn** | 400, 401, prompt quá dài | ❌ | sửa code, báo lỗi rõ ràng |
| **Lỗi tạm thời** | 429, 500, 503, 529, timeout | ✅ | exponential backoff + jitter |
| **Lỗi ngữ nghĩa** | output sai định dạng, thiếu field | ✅ có điều kiện | retry kèm phản hồi lỗi cho model |
| **Lỗi nghiệp vụ** | model từ chối trả lời | ❌ | fallback / chuyển người |

### 1.2 Exponential backoff + jitter

```
lần 1: chờ 1s   (+ ngẫu nhiên 0–1s)
lần 2: chờ 2s   (+ ngẫu nhiên 0–2s)
lần 3: chờ 4s   (+ ngẫu nhiên 0–4s)
```

**Jitter bắt buộc.** Không có nó, 100 request lỗi cùng lúc sẽ retry cùng lúc → đánh sập chính bạn ("thundering herd").

Nếu response có header `retry-after`, **luôn ưu tiên** con số đó.

### 1.3 Retry ngữ nghĩa — kỹ thuật quan trọng

Khi output sai định dạng, đừng retry mù. Hãy nói cho model biết nó sai gì:

```python
messages += [
    {"role": "assistant", "content": output_sai},
    {"role": "user", "content": f"Output trên không hợp lệ: {lỗi}. Hãy trả lời lại, CHỈ JSON."},
]
```

Tỉ lệ thành công lần 2 thường rất cao. Bạn sẽ dùng kỹ thuật này ở Ngày 30 và 55.

### 1.4 Ba lớp phòng thủ

```
1. TIMEOUT      → không bao giờ chờ vô hạn
2. RETRY        → chịu lỗi tạm thời
3. FALLBACK     → model phụ / câu trả lời mặc định / chuyển cho người
```

Thiếu lớp 3 nghĩa là khi provider down, sản phẩm của bạn cũng down.

### 1.5 Idempotency

Nếu retry một thao tác **có tác dụng phụ** (gửi tin nhắn cho khách!), bạn có thể gửi 3 lần. Giải pháp: mỗi thao tác có `idempotency_key`, kiểm tra trước khi thực hiện.

> Trong CareDesk-AI: gửi trùng tin nhắn cho khách là lỗi nhìn thấy được bằng mắt thường và làm mất uy tín. Ngày 74 sẽ làm kỹ.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Errors & rate limits | https://docs.anthropic.com/en/api/errors |
| AWS — Exponential backoff and jitter | https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/ |
| tenacity (thư viện retry) | https://tenacity.readthedocs.io/ |

---

## 3. Thực hành (80 phút)

`leanai_core/resilience.py`:

```python
"""Retry, fallback, circuit breaker."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass

import anthropic

RETRYABLE_EXC = (
    anthropic.RateLimitError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,
)


def with_retry(fn, *, max_attempts: int = 4, base: float = 1.0,
               max_wait: float = 30.0, on_retry=None):
    """Gọi fn() với exponential backoff + jitter."""
    last = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except RETRYABLE_EXC as e:
            last = e
            if attempt == max_attempts:
                break
            wait = min(base * 2 ** (attempt - 1), max_wait)
            wait += random.uniform(0, wait)            # jitter
            retry_after = getattr(getattr(e, "response", None), "headers", {})
            if retry_after:
                ra = retry_after.get("retry-after")
                if ra:
                    wait = float(ra)                   # server nói gì thì nghe nấy
            if on_retry:
                on_retry(attempt, e, wait)
            time.sleep(wait)
        except anthropic.BadRequestError:
            raise                                       # lỗi của bạn, retry vô ích
    raise RuntimeError(f"Thất bại sau {max_attempts} lần: {last}") from last


@dataclass
class CircuitBreaker:
    """Sau N lỗi liên tiếp thì ngừng gọi trong cooldown giây."""
    threshold: int = 5
    cooldown: float = 60.0
    failures: int = 0
    opened_at: float = 0.0

    def allow(self) -> bool:
        if self.failures < self.threshold:
            return True
        if time.time() - self.opened_at > self.cooldown:
            self.failures = 0                            # thử lại (half-open)
            return True
        return False

    def record(self, ok: bool) -> None:
        if ok:
            self.failures = 0
        else:
            self.failures += 1
            if self.failures == self.threshold:
                self.opened_at = time.time()
                print(f"  ⚡ Circuit OPEN: ngừng gọi {self.cooldown}s")


def with_fallback(primary, fallback, on_fallback=None):
    """Chạy primary, hỏng thì chạy fallback."""
    try:
        return primary()
    except Exception as e:
        if on_fallback:
            on_fallback(e)
        return fallback()
```

`exercises/day20/resilient.py` — test bằng lỗi giả:

```python
"""Ngày 20: test khả năng chịu lỗi bằng cách bơm lỗi nhân tạo."""
import random
import anthropic
from leanai_core.llm import LLMClient
from leanai_core.resilience import with_retry, with_fallback, CircuitBreaker


class FlakyLLM:
    """Bọc LLMClient, cố tình hỏng theo tỉ lệ để test."""
    def __init__(self, llm: LLMClient, fail_rate: float = 0.6):
        self.llm, self.fail_rate = llm, fail_rate
        self.attempts = 0

    def complete(self, prompt: str, **kw):
        self.attempts += 1
        if random.random() < self.fail_rate:
            raise anthropic.APITimeoutError(request=None)
        return self.llm.complete(prompt, **kw)


if __name__ == "__main__":
    random.seed(0)
    llm = LLMClient()
    flaky = FlakyLLM(llm, fail_rate=0.6)

    print("=== 1. Retry với backoff ===")
    r = with_retry(
        lambda: flaky.complete("RAG là gì? 1 câu.", tag="retry-test"),
        on_retry=lambda n, e, w: print(f"  lần {n} lỗi ({type(e).__name__}), chờ {w:.1f}s"))
    print(f"  Thành công sau {flaky.attempts} lần gọi: {r.text[:60]}")

    print("\n=== 2. Fallback sang model rẻ hơn ===")
    broken = FlakyLLM(llm, fail_rate=1.0)
    out = with_fallback(
        primary=lambda: with_retry(lambda: broken.complete("Xin chào"), max_attempts=2),
        fallback=lambda: "[FALLBACK] Hệ thống bận, nhân viên sẽ liên hệ lại.",
        on_fallback=lambda e: print(f"  primary chết ({type(e).__name__}) -> fallback"))
    print(f"  Kết quả: {out}")

    print("\n=== 3. Circuit breaker ===")
    cb = CircuitBreaker(threshold=3, cooldown=5)
    for i in range(8):
        if not cb.allow():
            print(f"  request {i}: BỊ CHẶN (circuit open)")
            continue
        try:
            broken.complete("test")
            cb.record(True)
        except Exception:
            cb.record(False)
            print(f"  request {i}: lỗi (đếm {cb.failures})")
```

---

## 4. Bài tập

**Bài 1 — Retry ngữ nghĩa.** Viết `complete_with_validation(prompt, validator, max_retries=2)`: nếu `validator(text)` trả về lỗi, gọi lại **kèm thông báo lỗi** trong messages. Test với validator yêu cầu output có đúng 3 dòng.

**Bài 2 — Idempotency.** Viết `IdempotentSender` lưu các `key` đã xử lý vào file JSON. Hàm `send(key, payload)` bỏ qua nếu key đã tồn tại. Chứng minh: gọi 3 lần cùng key chỉ "gửi" 1 lần.

**Bài 3 — Kịch bản sự cố.** Trong `progress/notes/day20.md`, trả lời:
*"Provider LLM down 30 phút vào 9h sáng. CareDesk-AI đang chạy job gửi tin cho 200 khách. Chuyện gì xảy ra với thiết kế hiện tại của bạn? Bạn cần thêm gì?"*
Gợi ý: hàng đợi, trạng thái job, khôi phục, thông báo cho người vận hành.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 20
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Retry có backoff **và jitter**, tôn trọng `retry-after`
- [ ] Không retry với lỗi 400/401
- [ ] Fallback hoạt động khi primary chết hoàn toàn
- [ ] Circuit breaker mở sau N lỗi, tự đóng sau cooldown
- [ ] Có `IdempotentSender` chứng minh chống gửi trùng
- [ ] Quiz ≥ 80%
