# NGÀY 54 — Tool result handling

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Đưa kết quả tool về cho LLM đúng cách — và kiểm soát để kết quả tool **không phá ngân sách context**.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Kết quả tool là input tính tiền

Mỗi lượt agent, **toàn bộ** lịch sử (gồm mọi kết quả tool trước đó) được gửi lại. Một agent 8 bước với tool trả 2.000 token mỗi lần → lượt cuối gửi hơn 16.000 token chỉ riêng kết quả tool.

```
Chi phí agent ≈ Σ (lịch sử tích luỹ tại mỗi bước)  →  tăng theo O(N²)
```

### 1.2 Bốn kỹ thuật nén kết quả tool

| Kỹ thuật | Cách làm |
|---|---|
| **Chọn trường** | chỉ trả trường model cần, bỏ trường thừa |
| **Tóm tắt kết quả lớn** | > 1.000 token → tóm tắt, giữ bản đầy đủ ở ngoài |
| **Tham chiếu** | trả `{"ref": "result_7", "preview": "..."}`, model xin chi tiết nếu cần |
| **Dọn lịch sử** | sau N bước, thay kết quả cũ bằng tóm tắt một dòng |

### 1.3 Định dạng kết quả

```python
# Tốt: JSON gọn, có đơn vị
{"buoi_con_lai": 4, "gia_tri_chua_dung": 4800000, "don_vi": "VND"}

# Lỗi: trả về text dài dòng
"Sau khi kiểm tra hệ thống, tôi thấy rằng khách hàng này hiện còn..."
```

### 1.4 Tool trả về lỗi — cách viết quan trọng

```python
{"error": "không tìm thấy khách C999",
 "hint": "dùng search_customers để tìm theo tên trước",
 "retryable": false}
```

`retryable` giúp vòng lặp agent biết nên thử lại hay đổi hướng (Ngày 55–56).

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Tool results | https://docs.anthropic.com/en/docs/build-with-claude/tool-use/implement-tool-use |
| Anthropic — Prompt caching (giảm chi phí lịch sử) | https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching |

---

## 3. Thực hành (80 phút)

`leanai_core/tool_result.py`:

```python
"""Xử lý và nén kết quả tool."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")
MAX_RESULT_TOKENS = 800


@dataclass
class ResultStore:
    """Giữ bản đầy đủ ngoài context, chỉ đưa tóm tắt vào prompt."""
    items: dict[str, str] = field(default_factory=dict)
    _n: int = 0

    def put(self, content: str) -> str:
        self._n += 1
        key = f"result_{self._n}"
        self.items[key] = content
        return key

    def get(self, key: str) -> str:
        return self.items.get(key, "")


def compress_result(content: str, store: ResultStore, llm=None,
                    max_tokens: int = MAX_RESULT_TOKENS) -> str:
    n = len(ENC.encode(content))
    if n <= max_tokens:
        return content

    key = store.put(content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, list):
        preview = json.dumps(data[:5], ensure_ascii=False)
        return json.dumps({"ref": key, "total_items": len(data),
                           "showing_first": 5, "preview": json.loads(preview),
                           "note": "kết quả bị cắt; dùng get_result_detail để xem thêm"},
                          ensure_ascii=False)

    if llm:
        s = llm.complete(
            f"Tóm tắt kết quả tool sau trong ≤120 từ, GIỮ NGUYÊN mọi con số quan trọng:\n"
            f"{content[:8000]}", temperature=0, max_tokens=250, tag="compress-tool").text
        return json.dumps({"ref": key, "original_tokens": n, "summary": s},
                          ensure_ascii=False)

    return json.dumps({"ref": key, "original_tokens": n,
                       "truncated": ENC.decode(ENC.encode(content)[:max_tokens])},
                      ensure_ascii=False)


def prune_history(messages: list[dict], keep_recent: int = 6) -> list[dict]:
    """Thay kết quả tool cũ bằng placeholder để giữ context gọn."""
    if len(messages) <= keep_recent:
        return messages
    out = []
    for i, m in enumerate(messages):
        if i >= len(messages) - keep_recent or not isinstance(m.get("content"), list):
            out.append(m); continue
        new_content = []
        for b in m["content"]:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                txt = str(b.get("content", ""))[:100]
                new_content.append({**b, "content": f"[kết quả cũ đã rút gọn] {txt}..."})
            else:
                new_content.append(b)
        out.append({**m, "content": new_content})
    return out
```

`exercises/day54/result_budget.py`:

```python
"""Ngày 54: đo chi phí agent có và không nén kết quả tool."""
import json
import tiktoken
from anthropic import Anthropic

from leanai_core.config import cfg
from leanai_core.tool_result import ResultStore, compress_result, prune_history
from exercises.day52.toolset import registry

ENC = tiktoken.get_encoding("cl100k_base")
client = Anthropic(api_key=cfg.ANTHROPIC_API_KEY)

BIG = [{"customer_id": f"C{i:03d}", "ten": f"Khách {i}", "sdt": f"09{i:08d}",
        "ghi_chu": "ghi chú dài " * 20, "vang_mat_ngay": 100 + i}
       for i in range(200)]


@registry.register("list_all_customers",
                   "Liệt kê TOÀN BỘ khách hàng. Kết quả rất lớn, cân nhắc dùng "
                   "list_overdue_customers nếu chỉ cần khách quá hạn.",
                   {"type": "object", "properties": {}, "required": []})
def list_all_customers():
    return BIG


def run(question: str, compress: bool, max_turns: int = 6):
    store = ResultStore()
    messages = [{"role": "user", "content": question}]
    total_in = 0
    for _ in range(max_turns):
        if compress:
            messages = prune_history(messages)
        r = client.messages.create(model=cfg.MODEL, max_tokens=900, temperature=0,
                                   tools=registry.api_tools(), messages=messages)
        total_in += r.usage.input_tokens
        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text"), total_in
        messages.append({"role": "assistant", "content": r.content})
        out = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            res = registry.execute(b.name, b.input)
            content = res.content if res.ok else json.dumps(
                {"error": res.error, "retryable": False}, ensure_ascii=False)
            raw = len(ENC.encode(content))
            if compress:
                content = compress_result(content, store)
            print(f"  {b.name}: {raw} token -> {len(ENC.encode(content))} token")
            out.append({"type": "tool_result", "tool_use_id": b.id,
                        "content": content, "is_error": not res.ok})
        messages.append({"role": "user", "content": out})
    return "[hết lượt]", total_in


Q = "Có bao nhiêu khách trong hệ thống và ai vắng mặt lâu nhất?"
for compress in (False, True):
    print(f"\n{'='*66}\nNÉN KẾT QUẢ: {compress}")
    ans, tokens = run(Q, compress)
    print(f"  Tổng input token: {tokens:,}")
    print(f"  Trả lời: {ans[:160]}")
```

---

## 4. Bài tập

**Bài 1 — Đo O(N²).** Chạy agent 2, 4, 6, 8 bước. Ghi tổng input token mỗi trường hợp. Xác nhận đường cong bậc hai.

**Bài 2 — Tool `get_result_detail`.** Thêm tool cho phép model xin chi tiết từ `ResultStore` theo `ref`. Model có tự dùng khi cần không?

**Bài 3 — Ngưỡng nén.** Thử `max_tokens` = 300, 800, 2000. Đo: chi phí giảm bao nhiêu, chất lượng câu trả lời có giảm không (chấm 10 câu hỏi).

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 54 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Kết quả tool lớn được nén, có `ref` truy xuất lại
- [ ] `prune_history` giảm context mà không làm agent mất phương hướng
- [ ] Có số liệu chi phí có nén vs không nén
- [ ] Lỗi tool trả về có `hint` và `retryable`
- [ ] Quiz ≥ 80%
