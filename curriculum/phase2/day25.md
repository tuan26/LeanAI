# NGÀY 25 — Constraints & format control

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Ép model tuân thủ ràng buộc **và tự động kiểm tra** — không tin lời model nói, chỉ tin code đo.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Ba lớp kiểm soát định dạng

```
LỚP 1 — PROMPT     : mô tả chính xác định dạng          (rẻ, ~85% hiệu quả)
LỚP 2 — PREFILL    : mồi sẵn phần đầu output            (rẻ, +10%)
LỚP 3 — VALIDATE   : code kiểm tra, sai thì retry       (bắt buộc cho production)
```

Chỉ có lớp 3 mới cho bạn **đảm bảo**. Lớp 1 và 2 giảm số lần phải retry.

### 1.2 Ràng buộc nào model tuân thủ tốt / kém

| Loại ràng buộc | Mức tuân thủ | Ghi chú |
|---|---|---|
| Cấu trúc (JSON, dòng, thẻ) | tốt | + prefill gần như hoàn hảo |
| Danh sách giá trị cho phép (enum) | tốt | phải liệt kê rõ |
| Số **mục** (đúng 3 gạch đầu dòng) | khá | đếm được → validate dễ |
| Số **từ** (tối đa 50 từ) | **kém** | model đếm từ rất tệ |
| Số **ký tự** | **rất kém** | do tokenization (Ngày 4) |
| Điều cấm (không dùng từ X) | khá | validate bằng regex |

> **Đừng dựa vào model đếm.** Ràng buộc độ dài phải được **code cắt hoặc code từ chối**, không phải model tự giác.

### 1.3 Mẹo thay thế cho ràng buộc độ dài

```
❌ "Viết tối đa 50 từ"
✅ "Viết 2-3 câu ngắn"                     ← model làm tốt hơn
✅ max_tokens=80 + stop_sequences          ← cắt cứng
✅ validate: nếu > 55 từ thì retry         ← đảm bảo
```

Kết hợp cả ba cho kết quả tốt nhất.

### 1.4 Stop sequences

```python
stop=["\n\n", "---", "</output>"]
```

Hữu ích khi model hay "nói thêm" sau khi đã xong việc. Tiết kiệm token thật.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Control response format | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prefill-claudes-response |
| Anthropic — Stop sequences | https://docs.anthropic.com/en/api/messages |

---

## 3. Thực hành (80 phút)

`leanai_core/validate.py`:

```python
"""Bộ kiểm tra ràng buộc + retry ngữ nghĩa."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Violation:
    rule: str
    detail: str


class Constraints:
    def __init__(self):
        self.checks: list = []

    def max_words(self, n: int):
        self.checks.append(lambda t: None if len(t.split()) <= n
                           else Violation("max_words", f"{len(t.split())} từ > {n}"))
        return self

    def exact_lines(self, n: int):
        def f(t):
            k = len([l for l in t.strip().splitlines() if l.strip()])
            return None if k == n else Violation("exact_lines", f"{k} dòng, cần {n}")
        self.checks.append(f)
        return self

    def forbidden(self, words: list[str]):
        def f(t):
            hit = [w for w in words if w.lower() in t.lower()]
            return Violation("forbidden", f"chứa từ cấm: {hit}") if hit else None
        self.checks.append(f)
        return self

    def must_match(self, pattern: str, label: str = ""):
        self.checks.append(lambda t: None if re.search(pattern, t, re.S)
                           else Violation("must_match", label or pattern))
        return self

    def enum_field(self, field: str, allowed: list[str]):
        def f(t):
            m = re.search(rf"{field}\s*:\s*(.+)", t)
            if not m:
                return Violation("enum_field", f"thiếu trường {field}")
            v = m.group(1).strip()
            return None if v in allowed else Violation("enum_field", f"{field}={v} không hợp lệ")
        self.checks.append(f)
        return self

    def max_emoji(self, n: int):
        def f(t):
            k = len(re.findall(r"[\U0001F300-\U0001FAFF☀-➿]", t))
            return None if k <= n else Violation("max_emoji", f"{k} emoji > {n}")
        self.checks.append(f)
        return self

    def run(self, text: str) -> list[Violation]:
        return [v for v in (c(text) for c in self.checks) if v]


def generate_valid(llm, prompt: str, constraints: Constraints, *,
                   system: str = "", max_retries: int = 2, **kw):
    """Sinh output thoả ràng buộc; sai thì báo lỗi lại cho model."""
    messages = [{"role": "user", "content": prompt}]
    for attempt in range(max_retries + 1):
        r = llm.chat(messages, system=system, tag=f"validate-try{attempt}", **kw)
        errs = constraints.run(r.text)
        if not errs:
            return r, attempt
        if attempt == max_retries:
            return r, attempt
        feedback = "; ".join(f"{e.rule}: {e.detail}" for e in errs)
        print(f"  [thử {attempt+1}] vi phạm: {feedback}")
        messages += [
            {"role": "assistant", "content": r.text},
            {"role": "user", "content":
             f"Output trên vi phạm ràng buộc: {feedback}. "
             f"Viết lại cho đúng, CHỈ trả về output, không giải thích."},
        ]
    return r, max_retries
```

`exercises/day25/constraints_test.py`:

```python
from leanai_core.llm import LLMClient
from leanai_core.validate import Constraints, generate_valid

llm = LLMClient()

SYS = """Bạn viết tin nhắn Zalo cho nhân viên spa gửi khách hàng.
QUY TẮC: xưng "em", gọi "chị/anh + tên"; 2-3 câu ngắn; nêu 1 lý do cụ thể;
kết bằng câu hỏi về thời gian.
CẤM: từ "khuyến mãi", "ưu đãi", "sốc", "giảm giá"; quá 1 emoji."""

CASES = [
 "Chị Lan, gói còn 4 buổi, hết hạn sau 25 ngày, 112 ngày chưa đến.",
 "Anh Hùng, gói massage còn 2 buổi, hết hạn 5 ngày nữa, từng phàn nàn giá.",
 "Chị Mai, mới mua gói 20 buổi, chưa dùng buổi nào, mua 40 ngày trước.",
]

rules = (Constraints()
         .max_words(55)
         .forbidden(["khuyến mãi", "ưu đãi", "sốc", "giảm giá"])
         .max_emoji(1)
         .must_match(r"\?", "phải có câu hỏi"))

stats = {"đạt lần 1": 0, "đạt sau retry": 0, "thất bại": 0}

for c in CASES:
    print(f"\n{'='*66}\n{c}")
    r, tries = generate_valid(llm, f"{c}\n\nViết tin nhắn.", rules,
                              system=SYS, temperature=0.7, max_tokens=200)
    errs = rules.run(r.text)
    print(f"-> {r.text}")
    if not errs:
        stats["đạt lần 1" if tries == 0 else "đạt sau retry"] += 1
        print(f"   ✓ đạt sau {tries} lần retry")
    else:
        stats["thất bại"] += 1
        print(f"   ✗ vẫn vi phạm: {[e.detail for e in errs]}")

print(f"\n{stats}")
print(llm.usage.report())
```

---

## 4. Bài tập

**Bài 1 — Đo tỉ lệ tuân thủ theo loại ràng buộc.** Chạy 20 case, thống kê ràng buộc nào bị vi phạm nhiều nhất. Kết quả có khớp bảng ở mục 1.2 không?

**Bài 2 — Chi phí của retry.** Đo: bao nhiêu % request cần retry, chi phí tăng bao nhiêu %. So với việc dùng prompt chặt hơn ngay từ đầu (thêm prefill + few-shot) — cách nào rẻ hơn?

**Bài 3 — Ràng buộc cho CareDesk-AI.** Viết bộ `Constraints` hoàn chỉnh cho tin nhắn gửi khách, gồm: độ dài, từ cấm, phải có tên khách, **không được chứa con số nào không có trong dữ liệu đầu vào** (ràng buộc cuối cùng này chính là lớp chống bịa của Ngày 13 — cài bằng regex trích số rồi đối chiếu).

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 25 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `Constraints` có ≥ 6 loại kiểm tra, dùng kiểu chuỗi (fluent)
- [ ] `generate_valid` retry kèm phản hồi lỗi, đạt ≥ 95% sau 2 lần
- [ ] Có bảng tỉ lệ vi phạm theo loại ràng buộc
- [ ] Ràng buộc "không có số lạ" hoạt động đúng
- [ ] Quiz ≥ 80%
