# NGÀY 51 — Function calling

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Cho LLM gọi được **một hàm Python thật** và hiểu chính xác cơ chế bên dưới.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 LLM không tự chạy hàm

Điều thật sự xảy ra:

```
1. Bạn gửi: câu hỏi + DANH SÁCH MÔ TẢ các tool
2. LLM trả về: "tôi muốn gọi get_customer(id='C001')"   ← chỉ là TEXT có cấu trúc
3. CODE CỦA BẠN chạy hàm đó                              ← bạn kiểm soát 100%
4. Bạn gửi kết quả về cho LLM
5. LLM dùng kết quả để trả lời
```

> LLM **không** có quyền chạy gì cả. Nó chỉ *đề nghị*. Mọi rủi ro an ninh nằm ở chỗ **code của bạn có kiểm tra trước khi chạy hay không**.

### 1.2 Vòng lặp tối thiểu

```
while True:
    response = llm.chat(messages, tools=tools)
    if response.stop_reason != "tool_use":
        break                                   # model đã trả lời xong
    for call in response.tool_calls:
        result = execute(call)                  # CODE của bạn
        messages.append(tool_result(call.id, result))
```

### 1.3 Tool schema

```python
{
  "name": "get_customer",
  "description": "Lấy hồ sơ khách hàng theo mã. Dùng khi cần biết gói dịch vụ, "
                 "lịch sử đến, hoặc thông tin liên hệ của một khách cụ thể.",
  "input_schema": {
      "type": "object",
      "properties": {
          "customer_id": {"type": "string", "description": "Mã khách, dạng C001"}
      },
      "required": ["customer_id"]
  }
}
```

**Description là prompt.** Model chọn tool dựa trên nó. Viết rõ: *làm gì*, *khi nào dùng*, *khi nào KHÔNG dùng*.

### 1.4 Vì sao tool quan trọng hơn RAG với dữ liệu động

| Câu hỏi | RAG | Tool |
|---|---|---|
| "chính sách hoàn tiền?" | ✅ | — |
| "khách C001 còn mấy buổi?" | ❌ dữ liệu thay đổi liên tục | ✅ query DB |
| "hôm nay có bao nhiêu lịch hẹn?" | ❌ | ✅ |

CareDesk-AI cần **cả hai**: RAG cho tri thức, tool cho dữ liệu sống.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Tool use | https://docs.anthropic.com/en/docs/build-with-claude/tool-use |
| Anthropic — Tool use examples | https://docs.anthropic.com/en/docs/build-with-claude/tool-use/implement-tool-use |

---

## 3. Thực hành (80 phút)

`leanai_core/tools.py`:

```python
"""Đăng ký và thực thi tool."""
from __future__ import annotations

import inspect
import json
import time
from dataclasses import dataclass, field
from typing import Callable

from .logging import log_event


@dataclass
class ToolResult:
    ok: bool
    content: str
    error: str = ""
    seconds: float = 0.0


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    fn: Callable
    requires_approval: bool = False        # dùng từ Ngày 61
    read_only: bool = True

    def to_api(self) -> dict:
        return {"name": self.name, "description": self.description,
                "input_schema": self.input_schema}


class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self.calls: list[dict] = []

    def register(self, name: str, description: str, input_schema: dict,
                 requires_approval: bool = False, read_only: bool = True):
        def deco(fn):
            self.tools[name] = Tool(name, description, input_schema, fn,
                                    requires_approval, read_only)
            return fn
        return deco

    def api_tools(self) -> list[dict]:
        return [t.to_api() for t in self.tools.values()]

    def execute(self, name: str, args: dict) -> ToolResult:
        t0 = time.time()
        tool = self.tools.get(name)
        if not tool:
            return ToolResult(False, "", f"tool '{name}' không tồn tại", 0.0)
        try:
            sig = inspect.signature(tool.fn)
            unknown = set(args) - set(sig.parameters)
            if unknown:
                return ToolResult(False, "", f"tham số lạ: {sorted(unknown)}",
                                  time.time() - t0)
            out = tool.fn(**args)
            content = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
            res = ToolResult(True, content, "", time.time() - t0)
        except Exception as e:
            res = ToolResult(False, "", f"{type(e).__name__}: {e}", time.time() - t0)

        self.calls.append({"name": name, "args": args, "ok": res.ok,
                           "error": res.error, "seconds": round(res.seconds, 3)})
        log_event("tool_call", tool=name, args=args, ok=res.ok,
                  error=res.error, seconds=round(res.seconds, 3))
        return res
```

`exercises/day51/first_tool.py`:

```python
"""Ngày 51: một tool, một vòng lặp."""
import json
from datetime import date

from anthropic import Anthropic
from leanai_core.config import cfg
from leanai_core.tools import ToolRegistry

registry = ToolRegistry()

DB = {
 "C001": {"ten": "Nguyễn Thị Lan", "goi": "Trị liệu da mặt 10 buổi",
          "da_dung": 6, "tong": 10, "het_han": "2026-10-12", "lan_cuoi": "2026-05-28"},
 "C002": {"ten": "Trần Văn Bình", "goi": "Massage 20 buổi",
          "da_dung": 0, "tong": 20, "het_han": "2027-03-01", "lan_cuoi": "2026-09-10"},
}


@registry.register(
    name="get_customer",
    description=("Lấy hồ sơ khách hàng theo mã khách. Dùng khi cần biết gói dịch vụ, "
                 "số buổi còn lại, ngày hết hạn hoặc lần cuối khách đến. "
                 "KHÔNG dùng để tìm khách theo tên — chỉ nhận mã dạng C001."),
    input_schema={"type": "object",
                  "properties": {"customer_id": {"type": "string",
                                                 "description": "Mã khách, dạng C001"}},
                  "required": ["customer_id"]})
def get_customer(customer_id: str) -> dict:
    c = DB.get(customer_id.upper())
    if not c:
        return {"error": f"không tìm thấy khách {customer_id}"}
    return {**c, "buoi_con_lai": c["tong"] - c["da_dung"],
            "hom_nay": date.today().isoformat()}


client = Anthropic(api_key=cfg.ANTHROPIC_API_KEY)


def run(question: str, max_turns: int = 5) -> str:
    messages = [{"role": "user", "content": question}]
    for turn in range(max_turns):
        r = client.messages.create(
            model=cfg.MODEL, max_tokens=1000, temperature=0,
            tools=registry.api_tools(), messages=messages)

        text = "".join(b.text for b in r.content if b.type == "text")
        if text:
            print(f"  [model] {text.strip()[:150]}")

        if r.stop_reason != "tool_use":
            return text

        messages.append({"role": "assistant", "content": r.content})
        results = []
        for block in r.content:
            if block.type != "tool_use":
                continue
            print(f"  [tool ] {block.name}({json.dumps(block.input, ensure_ascii=False)})")
            res = registry.execute(block.name, block.input)
            print(f"  [kết quả] {res.content[:120] if res.ok else 'LỖI: ' + res.error}")
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": res.content if res.ok else f"Lỗi: {res.error}",
                            "is_error": not res.ok})
        messages.append({"role": "user", "content": results})
    return "[đạt giới hạn số vòng]"


if __name__ == "__main__":
    for q in ["Khách C001 còn mấy buổi và hết hạn khi nào?",
              "So sánh tình trạng gói của C001 và C002, ai cần liên hệ gấp hơn?",
              "Khách C999 thế nào?",                       # test lỗi
              "Chính sách hoàn tiền của spa là gì?"]:      # không có tool -> model phải nói không biết
        print(f"\n{'='*70}\nHỏi: {q}")
        print(f"\nTrả lời: {run(q)}")
    print(f"\nTổng số lần gọi tool: {len(registry.calls)}")
```

---

## 4. Bài tập

**Bài 1 — Ba tool.** Thêm `get_appointments(date)` và `search_customers_by_name(name)`. Hỏi câu cần cả 3, xem model có tự phối hợp không.

**Bài 2 — Description là prompt.** Viết 2 phiên bản description cho `get_customer`: mơ hồ và rõ ràng. Chạy 10 câu hỏi, đếm số lần model chọn đúng tool. Chênh lệch bao nhiêu?

**Bài 3 — Ranh giới.** Hỏi câu **không** tool nào trả lời được. Model có bịa không? Có gọi tool sai không? Ghi lại — đây là hành vi bạn phải kiểm soát ở Ngày 62.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 51 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Một tool chạy được end-to-end
- [ ] `ToolRegistry` ghi log mọi lần gọi
- [ ] Giải thích được: LLM **không** tự chạy hàm
- [ ] Có số liệu chứng minh description ảnh hưởng việc chọn tool
- [ ] Tool lỗi không làm chết vòng lặp
- [ ] Quiz ≥ 80%
