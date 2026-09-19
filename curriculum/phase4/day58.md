# NGÀY 58 — State (trạng thái agent)

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Tách **trạng thái** ra khỏi lịch sử hội thoại, để agent có thể tạm dừng, khôi phục, và chờ người duyệt.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vì sao lịch sử hội thoại không đủ làm trạng thái

| Vấn đề | Hệ quả |
|---|---|
| Dài vô hạn | tốn tiền, vỡ context |
| Không truy vấn được | không biết "đã gửi tin cho ai chưa" |
| Không bền | restart server là mất hết |
| Không chờ được người | agent dừng để chờ duyệt thì mất ngữ cảnh |

### 1.2 Mô hình trạng thái

```python
AgentState:
    run_id          : định danh phiên
    status          : running | waiting_approval | completed | failed | cancelled
    goal            : mục tiêu ban đầu
    facts           : dữ liệu đã thu thập (từ tool)  ← nguồn sự thật
    plan            : các bước dự kiến / đã xong
    pending_action  : hành động đang chờ duyệt
    artifacts       : kết quả tạo ra (tin nhắn nháp, báo cáo)
    budget          : bước/chi phí đã dùng
    messages        : lịch sử (có thể nén)
```

> **Nguyên tắc:** `facts` là nguồn sự thật, không phải `messages`. Nén lịch sử không được làm mất facts (nhắc lại Ngày 18).

### 1.3 Máy trạng thái

```
        ┌──────────┐
   ┌───►│ RUNNING  │───── cần duyệt ────►┌──────────────────┐
   │    └────┬─────┘                     │ WAITING_APPROVAL │
   │         │ xong                      └────┬─────────────┘
   │         ▼                     approve    │    reject
   │   ┌───────────┐                 ┌────────┘       │
   │   │ COMPLETED │◄────────────────┘                ▼
   │   └───────────┘                          ┌────────────┐
   └── lỗi ──► FAILED                         │ CANCELLED  │
                                              └────────────┘
```

### 1.4 Bền vững hoá

Lưu state sau **mỗi bước** (JSON hoặc DB). Lợi ích: server restart giữa chừng vẫn tiếp tục được; và bạn có **audit trail** cho ngành y tế/tài chính.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Building effective agents | https://www.anthropic.com/research/building-effective-agents |
| Workflow state pattern | https://martinfowler.com/eaaDev/EventSourcing.html |

---

## 3. Thực hành (80 phút)

`leanai_core/state.py`:

```python
"""Trạng thái agent — bền vững, khôi phục được."""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

DB_PATH = Path("data/agent_state.db")


class Status(str, Enum):
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PendingAction:
    tool: str
    args: dict
    reason: str = ""
    preview: str = ""


@dataclass
class AgentState:
    goal: str
    tenant_id: str = ""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: Status = Status.RUNNING
    facts: dict = field(default_factory=dict)
    plan: list[dict] = field(default_factory=list)      # [{"step":..,"done":bool}]
    pending_action: dict | None = None
    artifacts: dict = field(default_factory=dict)
    steps_used: int = 0
    cost_used: float = 0.0
    messages: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""
    error: str = ""

    # ---- facts: nguồn sự thật ----
    def set_fact(self, key: str, value) -> None:
        self.facts[key] = value

    def fact_summary(self) -> str:
        if not self.facts:
            return ""
        return "DỮ LIỆU ĐÃ THU THẬP (chính xác, lấy từ hệ thống):\n" + "\n".join(
            f"- {k}: {json.dumps(v, ensure_ascii=False)[:300]}" for k, v in self.facts.items())

    # ---- chuyển trạng thái ----
    def request_approval(self, action: PendingAction) -> None:
        self.status = Status.WAITING_APPROVAL
        self.pending_action = asdict(action)

    def approve(self) -> dict | None:
        action, self.pending_action = self.pending_action, None
        self.status = Status.RUNNING
        return action

    def reject(self, reason: str = "") -> None:
        self.pending_action = None
        self.status = Status.CANCELLED
        self.error = reason

    def complete(self, result: str = "") -> None:
        self.status = Status.COMPLETED
        self.artifacts["final_answer"] = result

    def fail(self, error: str) -> None:
        self.status = Status.FAILED
        self.error = error

    def to_json(self) -> str:
        d = asdict(self)
        d["status"] = self.status.value
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "AgentState":
        d = json.loads(s)
        d["status"] = Status(d["status"])
        return cls(**d)


class StateStore:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS runs(
            run_id TEXT PRIMARY KEY, tenant_id TEXT, status TEXT,
            goal TEXT, state TEXT, updated_at TEXT)""")
        self.db.commit()

    def save(self, st: AgentState) -> None:
        st.updated_at = datetime.now(timezone.utc).isoformat()
        self.db.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?)",
                        (st.run_id, st.tenant_id, st.status.value, st.goal[:300],
                         st.to_json(), st.updated_at))
        self.db.commit()

    def load(self, run_id: str) -> AgentState | None:
        row = self.db.execute("SELECT state FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return AgentState.from_json(row[0]) if row else None

    def list_pending(self, tenant_id: str = "") -> list[tuple]:
        q = "SELECT run_id, goal, updated_at FROM runs WHERE status=?"
        args = [Status.WAITING_APPROVAL.value]
        if tenant_id:
            q += " AND tenant_id=?"; args.append(tenant_id)
        return self.db.execute(q + " ORDER BY updated_at", args).fetchall()
```

`exercises/day58/state_test.py`:

```python
from leanai_core.state import AgentState, StateStore, Status, PendingAction

store = StateStore()

st = AgentState(goal="Tìm khách quá hạn và soạn tin nhắn", tenant_id="clinic_001")
st.set_fact("khách quá hạn", [{"id": "C001", "ten": "Nguyễn Thị Lan", "vắng": 112}])
st.plan = [{"step": "tìm khách quá hạn", "done": True},
           {"step": "soạn tin nhắn", "done": True},
           {"step": "gửi tin", "done": False}]
st.artifacts["draft_message"] = "Chị Lan ơi, gói của chị còn 4 buổi..."
st.request_approval(PendingAction(
    tool="send_message",
    args={"customer_id": "C001", "channel": "zalo",
          "message": st.artifacts["draft_message"]},
    reason="Gửi tin nhắn thật cho khách — cần người duyệt",
    preview=st.artifacts["draft_message"]))
store.save(st)
print(f"run {st.run_id}: {st.status.value}")

print("\n=== Mô phỏng restart server ===")
del st
loaded = store.load(store.list_pending("clinic_001")[0][0])
print(f"Khôi phục run {loaded.run_id} | trạng thái {loaded.status.value}")
print(f"Facts còn nguyên: {list(loaded.facts)}")
print(f"Chờ duyệt: {loaded.pending_action['tool']}")
print(f"Nội dung xem trước: {loaded.pending_action['preview'][:60]}")

print("\n=== Người duyệt ===")
action = loaded.approve()
print(f"Đã duyệt -> thực thi {action['tool']}")
loaded.plan[-1]["done"] = True
loaded.complete("Đã gửi tin nhắn cho chị Lan")
store.save(loaded)
print(f"Trạng thái cuối: {loaded.status.value}")
print(f"Còn chờ duyệt: {store.list_pending('clinic_001')}")
```

---

## 4. Bài tập

**Bài 1 — Tích hợp vào Agent.** Sửa `Agent.run()` nhận và cập nhật `AgentState`, lưu sau mỗi bước. Thêm `Agent.resume(run_id)`.

**Bài 2 — Test khôi phục.** Chạy agent, kill process ở bước 4 (raise Exception). Khôi phục và chạy tiếp. Kết quả có đúng không? Facts có mất không?

**Bài 3 — Hàng chờ duyệt.** Viết CLI `python -m tools.approvals --tenant clinic_001` liệt kê mọi run đang chờ, cho phép approve/reject từng cái. Đây là tiền thân giao diện Ngày 87.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 58 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `AgentState` có đủ 5 trạng thái, chuyển đúng
- [ ] State lưu sau mỗi bước, khôi phục được sau khi kill
- [ ] Facts tách khỏi messages, không mất khi nén
- [ ] CLI liệt kê và duyệt được run đang chờ
- [ ] Quiz ≥ 80%
