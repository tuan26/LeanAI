# NGÀY 63 — Multi-step agent

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Agent chạy ổn định qua **5+ bước phụ thuộc nhau** — đo tỉ lệ hoàn thành, không chỉ "chạy được một lần".

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vì sao nhiều bước là khó

```
Mỗi bước đúng 95%  →  5 bước liên tiếp: 0.95⁵ = 77%
                   →  10 bước:          0.95¹⁰ = 60%
```

Độ tin cậy **giảm theo luỹ thừa**. Muốn agent 10 bước đạt 90%, mỗi bước phải đạt ~99%.

### 1.2 Bốn kỹ thuật tăng độ tin cậy

| Kỹ thuật | Cách làm |
|---|---|
| **Lập kế hoạch trước** | LLM viết kế hoạch, code kiểm tra tính hợp lệ trước khi chạy |
| **Checkpoint** | sau mỗi bước, lưu state; lỗi thì tiếp tục từ đó (Ngày 58) |
| **Xác minh từng bước** | kiểm tra kết quả bước N trước khi sang N+1 |
| **Giảm số bước** | gộp tool, dùng workflow cho phần cố định (Ngày 60) |

Kỹ thuật cuối là hiệu quả nhất: **agent 3 bước tin cậy hơn agent 10 bước**.

### 1.3 Plan-then-execute

```
1. LLM sinh kế hoạch:  [{"step":1,"tool":"...","why":"..."}, ...]
2. CODE kiểm tra:      tool có tồn tại? tham số hợp lệ? có tool ghi không?
3. Người duyệt kế hoạch (nếu có tool ghi)
4. CODE thực thi từng bước, cập nhật state
5. Nếu lệch: LLM lập lại kế hoạch với thông tin mới
```

Ưu điểm lớn: **người nhìn được kế hoạch trước khi nó chạy**.

### 1.4 Đo độ tin cậy đúng cách

Chạy **cùng một nhiệm vụ 10 lần**, đếm số lần thành công. Chạy một lần rồi kết luận "agent hoạt động" là tự lừa mình.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Building effective agents | https://www.anthropic.com/research/building-effective-agents |
| ReAct paper | https://arxiv.org/abs/2210.03629 |

---

## 3. Thực hành (80 phút)

`leanai_core/planner.py`:

```python
"""Plan-then-execute: LLM lập kế hoạch, code kiểm tra và thực thi."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .jsonutil import safe_json_loads
from .llm import LLMClient
from .tools import ToolRegistry

PLAN_PROMPT = """NHIỆM VỤ: {goal}

TOOL CÓ SẴN:
{tools}

DỮ LIỆU ĐÃ BIẾT:
{facts}

Lập kế hoạch ngắn nhất có thể để hoàn thành nhiệm vụ.
- Mỗi bước dùng ĐÚNG MỘT tool có trong danh sách.
- Nếu tham số của bước sau phụ thuộc kết quả bước trước, ghi "$stepN.field".
- Không thêm bước thừa. Nếu 2 bước là đủ, đừng viết 5 bước.
- Nếu nhiệm vụ không làm được với tool hiện có, trả về plan rỗng và ghi lý do.

CHỈ JSON:
{{"plan":[{{"step":1,"tool":"<tên>","args":{{}},"why":"<1 câu>"}}],
"reason_if_empty":""}}"""


@dataclass
class PlanStep:
    step: int
    tool: str
    args: dict
    why: str = ""
    result: str = ""
    ok: bool | None = None


@dataclass
class Plan:
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    reason_if_empty: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def has_write(self) -> bool:
        return any(s.tool for s in self.steps)      # kiểm tra thật ở validate

    def render(self) -> str:
        if not self.steps:
            return f"(không lập được kế hoạch) {self.reason_if_empty}"
        return "\n".join(f"  {s.step}. {s.tool}({json.dumps(s.args, ensure_ascii=False)[:60]})"
                         f"  — {s.why}" for s in self.steps)


class Planner:
    def __init__(self, llm: LLMClient, registry: ToolRegistry):
        self.llm, self.registry = llm, registry

    def plan(self, goal: str, facts: dict | None = None) -> Plan:
        tools = "\n".join(f"- {t.name}({', '.join(t.input_schema.get('properties', {}))}): "
                          f"{t.description[:110]}" for t in self.registry.tools.values())
        r = self.llm.complete(
            PLAN_PROMPT.format(goal=goal, tools=tools,
                               facts=json.dumps(facts or {}, ensure_ascii=False)[:1500]),
            temperature=0, max_tokens=900, tag="planner")
        d = safe_json_loads(r.text, {"plan": [], "reason_if_empty": "không parse được"})
        p = Plan(goal=goal, reason_if_empty=d.get("reason_if_empty", ""))
        for s in d.get("plan", []):
            p.steps.append(PlanStep(step=s.get("step", 0), tool=s.get("tool", ""),
                                    args=s.get("args", {}), why=s.get("why", "")))
        self.validate(p)
        return p

    def validate(self, p: Plan) -> None:
        for s in p.steps:
            t = self.registry.tools.get(s.tool)
            if not t:
                p.errors.append(f"bước {s.step}: tool '{s.tool}' không tồn tại")
                continue
            required = t.input_schema.get("required", [])
            missing = [k for k in required if k not in s.args]
            if missing:
                p.errors.append(f"bước {s.step}: thiếu tham số {missing}")

    def write_steps(self, p: Plan) -> list[PlanStep]:
        return [s for s in p.steps
                if (t := self.registry.tools.get(s.tool)) and not t.read_only]

    def execute(self, p: Plan, *, dry_run: bool = False) -> Plan:
        outputs: dict[int, dict] = {}
        for s in p.steps:
            args = {k: self._resolve(v, outputs) for k, v in s.args.items()}
            if dry_run:
                s.result, s.ok = "[dry run]", True
                continue
            res = self.registry.execute(s.tool, args)
            s.ok = res.ok and '"error"' not in res.content
            s.result = res.content[:400]
            try:
                outputs[s.step] = json.loads(res.content)
            except (json.JSONDecodeError, TypeError):
                outputs[s.step] = {"raw": res.content}
            if not s.ok:
                break                       # dừng chuỗi, giữ state để lập lại kế hoạch
        return p

    @staticmethod
    def _resolve(value, outputs: dict):
        if isinstance(value, str) and value.startswith("$step"):
            try:
                ref, field_ = value[5:].split(".", 1)
                data = outputs.get(int(ref), {})
                if isinstance(data, list) and data:
                    data = data[0]
                return data.get(field_, value)
            except (ValueError, AttributeError):
                return value
        return value
```

`exercises/day63/reliability.py`:

```python
"""Ngày 63: đo ĐỘ TIN CẬY — chạy mỗi nhiệm vụ 10 lần."""
from collections import Counter

from leanai_core.agent import Agent
from leanai_core.llm import LLMClient
from leanai_core.planner import Planner
from exercises.day52.toolset import registry

llm = LLMClient()
agent = Agent(registry, max_steps=12, max_cost=0.25)
planner = Planner(llm, registry)

TASKS = [
 ("1 bước", "Khách C001 còn mấy buổi?", lambda a: "4" in a),
 ("2 bước", "Chị Lan huỷ gói thì hoàn bao nhiêu tiền?",
  lambda a: "3.640.000" in a.replace(",", ".") or "3640000" in a.replace(".", "")),
 ("3 bước", "Khách quá hạn nào có giá trị lớn nhất, và nếu họ huỷ thì hoàn bao nhiêu?",
  lambda a: "Lan" in a),
 ("5 bước", "Với mỗi khách quá hạn trên 90 ngày: cho biết tên, số buổi còn lại, "
             "số tiền hoàn nếu huỷ, và soạn nháp tin nhắn (KHÔNG gửi).",
  lambda a: "Lan" in a and ("nháp" in a.lower() or "chị" in a.lower())),
]

N = 10
print(f"{'nhiệm vụ':<10} {'thành công':>12} {'bước TB':>9} {'$TB':>9} {'giây TB':>9}")
for name, goal, checker in TASKS:
    ok = 0; steps = []; costs = []; secs = []
    stops = Counter()
    for _ in range(N):
        run = agent.run(goal)
        ok += bool(checker(run.answer))
        steps.append(len([s for s in run.steps if s.kind == "tool"]))
        costs.append(run.cost); secs.append(run.seconds)
        stops[run.stop_reason] += 1
    print(f"{name:<10} {ok}/{N} = {ok/N:>5.0%} {sum(steps)/N:>9.1f} "
          f"{sum(costs)/N:>9.5f} {sum(secs)/N:>9.1f}   {dict(stops)}")

print("\n=== Plan-then-execute cho nhiệm vụ 5 bước ===")
p = planner.plan(TASKS[-1][1])
print("KẾ HOẠCH:\n" + p.render())
print(f"Lỗi kiểm tra: {p.errors or 'không'}")
print(f"Bước có tác dụng phụ: {[s.tool for s in planner.write_steps(p)] or 'không'}")
planner.execute(p, dry_run=True)
print(f"Dry run: {sum(1 for s in p.steps if s.ok)}/{len(p.steps)} bước hợp lệ")
```

---

## 4. Bài tập

**Bài 1 — Bảng độ tin cậy.** Chạy `reliability.py`. Ghi bảng: số bước vs tỉ lệ thành công. Đường cong có khớp lý thuyết 0.95ⁿ không?

**Bài 2 — Giảm số bước.** Với nhiệm vụ 5 bước, thêm một tool gộp (`get_overdue_with_refund`). Đo lại tỉ lệ thành công. Cải thiện bao nhiêu?

**Bài 3 — Lập lại kế hoạch.** Khi một bước thất bại, gọi `planner.plan()` lại với facts mới. Đo tỉ lệ phục hồi trên 10 lần chạy có lỗi nhân tạo.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 63 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Đo độ tin cậy bằng cách chạy **10 lần/nhiệm vụ**
- [ ] Nhiệm vụ 5 bước đạt ≥ 70% thành công
- [ ] Planner kiểm tra kế hoạch bằng code trước khi chạy
- [ ] Dry run hoạt động, hiện rõ bước nào có tác dụng phụ
- [ ] Chứng minh được: giảm số bước tăng độ tin cậy
- [ ] Quiz ≥ 80%
