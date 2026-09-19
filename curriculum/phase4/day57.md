# NGÀY 57 — Agent loop

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Viết `Agent` class hoàn chỉnh của riêng bạn — không dùng framework. Đây là lớp lõi bạn dùng đến Ngày 90.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Agent = vòng lặp + tool + điều kiện dừng

```
while chưa xong và chưa hết ngân sách:
    1. Gửi (system + lịch sử + tool) cho LLM
    2. Nếu LLM trả lời text  → XONG
    3. Nếu LLM gọi tool      → kiểm tra → thực thi → thêm kết quả vào lịch sử
    4. Quay lại bước 1
```

Framework (LangChain, LlamaIndex...) chỉ là lớp bọc quanh vòng lặp này. Tự viết một lần → bạn debug được mọi framework sau này.

### 1.2 Năm điều kiện dừng bắt buộc

```
1. Model trả lời text (stop_reason != tool_use)   ← bình thường
2. Vượt số bước tối đa
3. Vượt ngân sách chi phí
4. Quá số lỗi liên tiếp
5. Cần người duyệt (Ngày 61)
```

Thiếu điều kiện 2–4 = agent có thể chạy vô hạn và đốt tiền.

### 1.3 System prompt cho agent

Khác prompt thường — phải nói rõ **cách làm việc**:

```
- Lập kế hoạch ngắn trước khi gọi tool
- Mỗi bước chỉ làm một việc
- Dùng tool để lấy dữ liệu, KHÔNG tự nhớ hay tự tính
- Nếu tool lỗi 2 lần, đổi cách tiếp cận
- Khi đủ thông tin, dừng lại và trả lời
- Không bao giờ bịa dữ liệu không lấy được từ tool
```

### 1.4 Agent trả về gì

Không chỉ text. Phải trả về **cả quá trình**: các bước, tool đã gọi, chi phí, lý do dừng. Không có nó thì không debug được (Ngày 64) và không đánh giá được (Ngày 66).

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Building effective agents | https://www.anthropic.com/research/building-effective-agents |
| Anthropic — Tool use | https://docs.anthropic.com/en/docs/build-with-claude/tool-use |

---

## 3. Thực hành (80 phút)

`leanai_core/agent.py`:

```python
"""Agent loop — lớp lõi dùng đến Ngày 90."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from anthropic import Anthropic

from .config import cfg
from .logging import log_event
from .tool_guard import LoopGuard
from .tool_result import compress_result, ResultStore
from .tools import ToolRegistry

AGENT_SYSTEM = """VAI TRÒ: trợ lý vận hành cho chuỗi phòng khám/spa tại Việt Nam.
Bạn hỗ trợ NHÂN VIÊN, không nói chuyện trực tiếp với khách hàng.

CÁCH LÀM VIỆC:
- Trước khi gọi tool, nói ngắn gọn bạn định làm gì (1 câu).
- Mỗi bước chỉ làm MỘT việc.
- Mọi dữ liệu phải lấy từ tool. TUYỆT ĐỐI không tự nhớ, không tự tính toán tiền bạc.
- Nếu một tool lỗi 2 lần, hãy đổi cách tiếp cận khác.
- Khi đã đủ thông tin, DỪNG gọi tool và đưa ra câu trả lời cuối.
- Nếu không làm được, nói rõ vì sao và cần gì thêm.

CẤM: bịa số liệu; hành động ghi (gửi tin, đổi lịch) khi chưa được xác nhận rõ ràng."""


@dataclass
class Step:
    n: int
    kind: str                  # think | tool | answer | blocked
    content: str = ""
    tool: str = ""
    args: dict = field(default_factory=dict)
    ok: bool = True
    seconds: float = 0.0


@dataclass
class AgentRun:
    question: str
    answer: str = ""
    steps: list[Step] = field(default_factory=list)
    stop_reason: str = ""
    cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0

    @property
    def tool_calls(self) -> list[str]:
        return [s.tool for s in self.steps if s.kind == "tool"]

    def trace(self) -> str:
        out = [f"Q: {self.question}"]
        for s in self.steps:
            if s.kind == "tool":
                flag = "✓" if s.ok else "✗"
                out.append(f"  [{s.n}] {flag} {s.tool}"
                           f"({json.dumps(s.args, ensure_ascii=False)[:70]}) "
                           f"{s.seconds:.2f}s")
            elif s.kind == "think":
                out.append(f"  [{s.n}] 💭 {s.content[:90]}")
            elif s.kind == "blocked":
                out.append(f"  [{s.n}] 🛑 {s.content[:90]}")
        out.append(f"  => {self.answer[:150]}")
        out.append(f"  dừng vì: {self.stop_reason} | {len(self.steps)} bước | "
                   f"${self.cost:.5f} | {self.seconds:.1f}s")
        return "\n".join(out)


class Agent:
    def __init__(self, registry: ToolRegistry, *, system: str = AGENT_SYSTEM,
                 model: str | None = None, max_steps: int = 12,
                 max_cost: float = 0.30, temperature: float = 0.0,
                 compress_results: bool = True):
        self.client = Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
        self.registry = registry
        self.system = system
        self.model = model or cfg.MODEL
        self.max_steps = max_steps
        self.max_cost = max_cost
        self.temperature = temperature
        self.compress = compress_results

    def run(self, question: str, extra_context: str = "") -> AgentRun:
        run = AgentRun(question=question)
        guard = LoopGuard(max_steps=self.max_steps, max_cost=self.max_cost)
        store = ResultStore()
        content = f"{extra_context}\n\n{question}" if extra_context else question
        messages = [{"role": "user", "content": content}]
        t_start = time.time()
        n = 0

        while True:
            blocked = guard.check_step()
            if blocked:
                run.stop_reason = "guard"
                n += 1
                run.steps.append(Step(n, "blocked", blocked))
                messages.append({"role": "user", "content":
                                 blocked + " Hãy tổng kết những gì đã biết và dừng lại."})
                r = self._call(messages)
                run.answer = self._text(r)
                self._account(run, r)
                break

            r = self._call(messages)
            self._account(run, r)
            guard.cost = run.cost

            text = self._text(r)
            if text.strip():
                n += 1
                run.steps.append(Step(n, "think", text.strip()))

            if r.stop_reason != "tool_use":
                run.answer = text
                run.stop_reason = "completed"
                break

            messages.append({"role": "assistant", "content": r.content})
            results = []
            for b in r.content:
                if b.type != "tool_use":
                    continue
                n += 1
                stop = guard.check_call(b.name, b.input)
                if stop:
                    run.steps.append(Step(n, "blocked", stop, tool=b.name, args=b.input,
                                          ok=False))
                    results.append({"type": "tool_result", "tool_use_id": b.id,
                                    "content": stop, "is_error": True})
                    continue

                t0 = time.time()
                res = self.registry.execute(b.name, b.input)
                dt = time.time() - t0
                ok = res.ok and '"error"' not in res.content
                guard.record(ok)
                out = res.content if res.ok else json.dumps(
                    {"error": res.error, "retryable": False}, ensure_ascii=False)
                if self.compress:
                    out = compress_result(out, store)
                run.steps.append(Step(n, "tool", out[:200], b.name, b.input, ok, dt))
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": out, "is_error": not ok})
            messages.append({"role": "user", "content": results})

        run.seconds = time.time() - t_start
        log_event("agent_run", question=question[:100], steps=len(run.steps),
                  tools=run.tool_calls, stop_reason=run.stop_reason,
                  cost=round(run.cost, 6), seconds=round(run.seconds, 2))
        return run

    # ---- helpers ----
    def _call(self, messages):
        return self.client.messages.create(
            model=self.model, max_tokens=1500, temperature=self.temperature,
            system=self.system, tools=self.registry.api_tools(), messages=messages)

    @staticmethod
    def _text(r) -> str:
        return "".join(b.text for b in r.content if b.type == "text")

    def _account(self, run: AgentRun, r) -> None:
        run.input_tokens += r.usage.input_tokens
        run.output_tokens += r.usage.output_tokens
        run.cost += (r.usage.input_tokens * cfg.PRICE_IN
                     + r.usage.output_tokens * cfg.PRICE_OUT) / 1e6
```

`exercises/day57/agent_test.py`:

```python
from leanai_core.agent import Agent
from exercises.day52.toolset import registry

agent = Agent(registry, max_steps=10, max_cost=0.20)

for q in ["Khách nào đang có nguy cơ mất doanh thu nhất? Giải thích bằng số liệu.",
          "Chị Lan nếu huỷ gói thì được hoàn bao nhiêu?",
          "Ngày mai có lịch hẹn nào không, khách đó tình trạng gói thế nào?",
          "Doanh thu tháng trước là bao nhiêu?"]:      # không có tool -> phải nói không biết
    print("\n" + "=" * 74)
    print(agent.run(q).trace())
```

---

## 4. Bài tập

**Bài 1 — Bộ test agent.** Tạo 15 nhiệm vụ: 5 đơn giản (1 tool), 5 nhiều bước, 5 không làm được. Chạy, ghi bảng: số bước, tool dùng, đúng/sai, chi phí, lý do dừng.

**Bài 2 — Ảnh hưởng của system prompt.** Bỏ phần "CÁCH LÀM VIỆC" khỏi system prompt. Đo lại số bước trung bình và tỉ lệ đúng. Chênh lệch bao nhiêu?

**Bài 3 — Ngân sách.** Đặt `max_steps=3` cho nhiệm vụ cần 6 bước. Agent có tổng kết được phần đã làm không, hay chết giữa chừng?

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 57 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `Agent` class chạy được, không dùng framework
- [ ] Có đủ 5 điều kiện dừng
- [ ] `trace()` in ra đủ để debug
- [ ] Nhiệm vụ không làm được → agent nói rõ, không bịa
- [ ] Có bảng kết quả 15 nhiệm vụ
- [ ] Quiz ≥ 80%
