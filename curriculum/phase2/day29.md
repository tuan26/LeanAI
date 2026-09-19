# NGÀY 29 — JSON output

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Đạt **100% output parse được** — vì một JSON hỏng trong production nghĩa là một request chết.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vì sao JSON hỏng

| Nguyên nhân | Ví dụ |
|---|---|
| Rào đón | `Dưới đây là JSON bạn cần:\n{...}` |
| Bọc markdown | ` ```json\n{...}\n``` ` |
| Dấu phẩy thừa | `{"a":1,}` |
| Nháy đơn | `{'a': 1}` |
| Nháy thông minh | `{"a": "abc"}` với " " |
| Bị cắt | `stop_reason == "max_tokens"` (Ngày 16!) |
| Chữ sau JSON | `{...}\n\nHy vọng hữu ích!` |

### 1.2 Bốn kỹ thuật ổn định JSON — dùng **cùng lúc**

```
1. PROMPT     : "CHỈ trả về JSON, không giải thích, không markdown"
2. PREFILL    : assistant bắt đầu bằng "{"              ← diệt phần rào đón
3. STOP       : stop_sequences=["}\n\n", "```"]          ← chặn phần thừa
4. PARSE MỀM  : gỡ fence, tìm khối {...} cân bằng, sửa lỗi phổ biến
```

Kết hợp 4 cái này thường đạt ~99%. 1% còn lại xử lý bằng retry ngữ nghĩa (Ngày 20).

### 1.3 Thiết kế schema tốt

| Nguyên tắc | Vì sao |
|---|---|
| Trường phẳng hơn là lồng sâu | model dễ sai ở cấu trúc lồng nhiều tầng |
| Dùng enum thay vì text tự do | validate được, thống kê được |
| Luôn có trường `confidence` | biết khi nào cần người kiểm tra |
| Luôn có `"KHÔNG_XÁC_ĐỊNH"` trong enum | cho model lối thoát thay vì bịa (Ngày 13) |
| Tên trường bằng tiếng Anh, giá trị tiếng Việt | tránh lỗi mã hoá, dễ map sang DB |
| Không để model tự tính số | đã học ở Ngày 26 |

### 1.4 Ví dụ schema tốt vs tồi

```jsonc
// ❌ tồi
{"analysis": "khách hàng này có vẻ sắp rời bỏ vì đã lâu không quay lại..."}

// ✅ tốt
{
  "opportunity_type": "OVERDUE_REVISIT",        // enum
  "confidence": "HIGH",                          // enum: HIGH|MEDIUM|LOW
  "evidence": ["vắng 112 ngày", "còn 4 buổi"],   // mảng, trích từ nguồn
  "recommended_action": "SEND_ZALO",             // enum
  "needs_human_review": false,                   // boolean
  "reason_if_uncertain": null
}
```

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Increase output consistency (JSON) | https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency |
| JSON Schema | https://json-schema.org/learn/getting-started-step-by-step |

---

## 3. Thực hành (80 phút)

`leanai_core/jsonutil.py` (hoàn thiện từ Ngày 15):

```python
"""Parse JSON từ output LLM một cách bền bỉ."""
from __future__ import annotations

import json
import re


def strip_fence(text: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    return m.group(1) if m else text


def extract_balanced(text: str, open_ch="{", close_ch="}") -> str | None:
    """Tìm khối JSON cân bằng đầu tiên, bỏ qua ngoặc nằm trong chuỗi."""
    start = text.find(open_ch)
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if esc:
            esc = False; continue
        if ch == "\\":
            esc = True; continue
        if ch == '"':
            in_str = not in_str; continue
        if in_str:
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def repair(text: str) -> str:
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r",\s*([}\]])", r"\1", text)          # dấu phẩy thừa
    text = re.sub(r"(?<![\\])'([^']*?)'(\s*:)", r'"\1"\2', text)   # khoá nháy đơn
    return text


def safe_json_loads(text: str, default=None, *, verbose: bool = False):
    for stage, candidate in (
        ("raw", text),
        ("fence", strip_fence(text)),
        ("balanced", extract_balanced(strip_fence(text)) or ""),
        ("repaired", repair(extract_balanced(strip_fence(text)) or "")),
        ("array", extract_balanced(strip_fence(text), "[", "]") or ""),
    ):
        if not candidate.strip():
            continue
        try:
            out = json.loads(candidate)
            if verbose and stage != "raw":
                print(f"  [json] phải dùng tầng '{stage}'")
            return out
        except json.JSONDecodeError:
            continue
    if verbose:
        print(f"  [json] THẤT BẠI: {text[:120]!r}")
    return default


def json_complete(llm, prompt: str, *, system: str = "", schema_hint: str = "",
                  max_retries: int = 2, **kw):
    """Gọi LLM và đảm bảo trả về dict. Dùng prefill + stop + retry."""
    full = prompt + (f"\n\nTrả về CHỈ JSON theo schema:\n{schema_hint}" if schema_hint else
                     "\n\nTrả về CHỈ JSON, không giải thích, không markdown.")
    messages = [{"role": "user", "content": full},
                {"role": "assistant", "content": "{"}]        # prefill
    for attempt in range(max_retries + 1):
        r = llm.chat(messages, system=system, stop=["\n\n\n"],
                     tag=f"json-try{attempt}", **kw)
        raw = "{" + r.text if not r.text.lstrip().startswith("{") else r.text
        if r.truncated:
            print("  ⚠ output bị cắt — tăng max_tokens")
        data = safe_json_loads(raw, None, verbose=True)
        if data is not None:
            return data, attempt
        if attempt < max_retries:
            messages = [{"role": "user", "content": full},
                        {"role": "assistant", "content": raw[:500]},
                        {"role": "user", "content":
                         "Output trên không phải JSON hợp lệ. Trả lời lại, "
                         "CHỈ JSON thuần, bắt đầu bằng { và kết thúc bằng }."}]
    return None, max_retries
```

`exercises/day29/json_bench.py`:

```python
"""Ngày 29: đo tỉ lệ parse thành công của 4 chiến lược."""
from leanai_core.llm import LLMClient
from leanai_core.jsonutil import safe_json_loads, json_complete

llm = LLMClient()

SCHEMA = """{
  "opportunity_type": "OVERDUE_REVISIT|UNUSED_PACKAGE|EXPIRING_SOON|VIP_SILENT|NONE",
  "confidence": "HIGH|MEDIUM|LOW",
  "evidence": ["<trích dẫn ngắn từ dữ liệu>"],
  "recommended_action": "SEND_ZALO|CALL|WAIT|ESCALATE",
  "needs_human_review": true|false
}"""

CASES = [
 "Chị Lan: gói còn 4/10 buổi, hết hạn 25 ngày nữa, vắng 112 ngày, chi tiêu 38tr.",
 "Anh Bình: mới mua gói 20 buổi hôm qua, chưa dùng buổi nào.",
 "Chị Hoa: gói đã dùng hết, vắng 200 ngày, từng khiếu nại gay gắt tháng trước.",
 "Anh Nam: gói còn 1 buổi, hết hạn 2 ngày nữa, tuần trước vừa đến.",
 "Chị Thu: dữ liệu thiếu ngày mua gói, không rõ hạn dùng.",
]

def run(strategy: str) -> int:
    ok = 0
    for c in CASES:
        prompt = f"<data>{c}</data>\n\nPhân tích cơ hội doanh thu."
        if strategy == "naive":
            r = llm.complete(prompt + f"\nTrả về JSON theo schema: {SCHEMA}",
                             temperature=0, max_tokens=400, tag=strategy)
            d = safe_json_loads(r.text)
        elif strategy == "soft_parse":
            r = llm.complete(prompt + f"\nCHỈ trả về JSON: {SCHEMA}",
                             temperature=0, max_tokens=400, tag=strategy)
            d = safe_json_loads(r.text, verbose=True)
        else:   # full
            d, _ = json_complete(llm, prompt, schema_hint=SCHEMA,
                                 temperature=0, max_tokens=400)
        ok += d is not None
        print(f"  {'✓' if d else '✗'} {c[:45]} -> {str(d)[:90]}")
    return ok

for s in ("naive", "soft_parse", "full"):
    print(f"\n=== {s} ===")
    print(f"Parse thành công: {run(s)}/{len(CASES)}")

print("\n" + llm.usage.report())
```

---

## 4. Bài tập

**Bài 1 — Bộ test parser.** Tạo 15 chuỗi JSON hỏng theo 7 nguyên nhân ở mục 1.1. Chạy `safe_json_loads` trên tất cả. Mục tiêu: **≥ 13/15** cứu được. Cái nào không cứu được → giải thích vì sao và khi nào nên bỏ cuộc thay vì sửa liều.

**Bài 2 — 50 lần chạy.** Chạy chiến lược `full` 50 lần trên cùng một case. Đo: tỉ lệ parse 100%? Số lần phải retry? Chi phí trung bình? Nếu chưa đạt 100%, tìm nguyên nhân còn lại.

**Bài 3 — Schema cho CareDesk-AI.** Viết `templates/schemas/opportunity.json` — schema đầy đủ cho một cơ hội doanh thu, đúng 6 nguyên tắc ở mục 1.3. Đây là schema bạn sẽ dùng thật ở Ngày 82–84.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 29 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `safe_json_loads` cứu được ≥ 13/15 chuỗi hỏng
- [ ] Chiến lược `full` đạt 100% parse trên 50 lần chạy
- [ ] Phát hiện và cảnh báo được trường hợp output bị cắt
- [ ] Có `templates/schemas/opportunity.json` đúng 6 nguyên tắc
- [ ] Quiz ≥ 80%
