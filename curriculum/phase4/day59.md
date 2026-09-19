# NGÀY 59 — Memory (ngắn hạn & dài hạn)

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Agent nhớ được qua nhiều phiên — nhưng chỉ nhớ **đúng thứ đáng nhớ**.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Bốn loại bộ nhớ

| Loại | Phạm vi | Lưu ở đâu | Ví dụ |
|---|---|---|---|
| **Working** | trong 1 lượt | messages | kết quả tool vừa gọi |
| **Episodic** | trong 1 phiên | AgentState.facts | "đã tìm được 3 khách quá hạn" |
| **Semantic** | lâu dài, chia sẻ | vector DB / bảng | "chính sách hoàn tiền là 80%" |
| **Procedural** | lâu dài | code/prompt | "quy trình xử lý khiếu nại" |

### 1.2 Nguyên tắc quyết định nhớ gì

```
Nhớ khi:  sự thật ỔN ĐỊNH + có ích cho phiên sau + không suy ra được từ DB
Đừng nhớ: dữ liệu thay đổi liên tục (số buổi còn lại) → luôn gọi tool
          thứ đã có trong DB → truy vấn, đừng sao chép
          suy đoán của model → chỉ nhớ sự kiện, không nhớ ý kiến
```

> Ghi nhớ sai còn tệ hơn không nhớ. Một memory "khách Lan không thích gọi điện" ghi nhầm sẽ ảnh hưởng mọi phiên sau.

### 1.3 Ba thao tác của bộ nhớ dài hạn

```
WRITE   : trích sự kiện đáng nhớ từ phiên, có confidence
RETRIEVE: tìm memory liên quan với truy vấn hiện tại (dùng embedding)
UPDATE  : khi memory mới mâu thuẫn memory cũ → cập nhật, giữ lịch sử
```

Bước UPDATE hay bị bỏ qua và là nguồn gốc của "AI nhớ thông tin lỗi thời".

### 1.4 Memory có nguồn gốc

Mỗi memory phải ghi: nhớ từ phiên nào, dựa trên tool nào, lúc nào, confidence bao nhiêu. Không có nó thì không kiểm chứng được và không xoá đúng được.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Building effective agents | https://www.anthropic.com/research/building-effective-agents |
| MemGPT paper (ý tưởng phân tầng bộ nhớ) | https://arxiv.org/abs/2310.08560 |

---

## 3. Thực hành (80 phút)

`leanai_core/memory_store.py`:

```python
"""Bộ nhớ dài hạn cho agent — có nguồn gốc, có cập nhật."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .embedding import EmbeddingService
from .jsonutil import safe_json_loads
from .llm import LLMClient

DB_PATH = Path("data/agent_memory.db")

EXTRACT_PROMPT = """<phiên_làm_việc>
{transcript}
</phiên_làm_việc>

Trích các SỰ KIỆN đáng nhớ lâu dài về khách hàng hoặc quy trình.

CHỈ nhớ nếu: (a) là sự kiện ổn định, không thay đổi hàng ngày;
(b) có ích cho lần làm việc sau; (c) được chứng minh bởi dữ liệu trong phiên.

KHÔNG nhớ: số buổi còn lại, số dư, ngày hết hạn (luôn tra lại từ hệ thống);
suy đoán, ý kiến chủ quan; thông tin đã có sẵn trong cơ sở dữ liệu.

CHỈ JSON: {{"memories":[{{"subject":"<vd C001 hoặc quy_trinh>","fact":"<1 câu>",
"confidence":"HIGH|MEDIUM|LOW","evidence":"<dựa trên đâu>"}}]}}
Nếu không có gì đáng nhớ: {{"memories": []}}"""


@dataclass
class Memory:
    subject: str
    fact: str
    confidence: str = "MEDIUM"
    evidence: str = ""
    run_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    superseded_by: str = ""


class MemoryStore:
    def __init__(self, tenant_id: str, path: Path = DB_PATH,
                 embedder: EmbeddingService | None = None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS memories(
            id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT, subject TEXT,
            fact TEXT, confidence TEXT, evidence TEXT, run_id TEXT,
            created_at TEXT, superseded_by TEXT DEFAULT '')""")
        self.db.commit()
        self.tenant = tenant_id
        self.emb = embedder or EmbeddingService()

    def write(self, m: Memory) -> int:
        cur = self.db.execute(
            "INSERT INTO memories(tenant_id,subject,fact,confidence,evidence,run_id,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (self.tenant, m.subject, m.fact, m.confidence, m.evidence,
             m.run_id, m.created_at))
        self.db.commit()
        return cur.lastrowid

    def active(self, subject: str = "") -> list[tuple]:
        q = ("SELECT id,subject,fact,confidence,created_at FROM memories "
             "WHERE tenant_id=? AND superseded_by=''")
        args = [self.tenant]
        if subject:
            q += " AND subject=?"; args.append(subject)
        return self.db.execute(q + " ORDER BY created_at DESC", args).fetchall()

    def retrieve(self, query: str, k: int = 5, subject: str = "") -> list[str]:
        rows = self.active(subject)
        if not rows:
            return []
        qv = self.emb.embed(query)
        vecs = self.emb.embed([r[2] for r in rows])
        scored = sorted(zip(rows, (float(qv @ v) for v in vecs)),
                        key=lambda x: -x[1])[:k]
        return [f"{r[1]}: {r[2]} (nhớ {r[4][:10]}, {r[3]})" for r, _ in scored]

    def supersede(self, old_id: int, new: Memory) -> int:
        new_id = self.write(new)
        self.db.execute("UPDATE memories SET superseded_by=? WHERE id=?",
                        (str(new_id), old_id))
        self.db.commit()
        return new_id

    def extract_from_run(self, llm: LLMClient, transcript: str, run_id: str) -> list[Memory]:
        r = llm.complete(EXTRACT_PROMPT.format(transcript=transcript[:6000]),
                         temperature=0, max_tokens=700, tag="memory-extract")
        out = []
        for d in safe_json_loads(r.text, {"memories": []}).get("memories", []):
            if d.get("confidence") == "LOW":
                continue                                   # không nhớ thứ không chắc
            m = Memory(subject=d.get("subject", ""), fact=d.get("fact", ""),
                       confidence=d.get("confidence", "MEDIUM"),
                       evidence=d.get("evidence", ""), run_id=run_id)
            if m.fact:
                self.write(m); out.append(m)
        return out
```

`exercises/day59/memory_test.py`:

```python
from leanai_core.llm import LLMClient
from leanai_core.memory_store import MemoryStore, Memory

llm = LLMClient()
ms = MemoryStore("clinic_001")

TRANSCRIPT = """
Nhân viên: Gửi tin cho chị Lan C001 nhé.
Agent: [get_customer C001] Chị Lan còn 4/10 buổi, vắng 112 ngày, hết hạn 12/10/2026.
Nhân viên: Chị này không thích gọi điện đâu, chỉ nhắn Zalo thôi. Lần trước gọi chị khó chịu.
Agent: Đã ghi nhận. Soạn tin Zalo.
Nhân viên: Mà khung giờ sáng chị mới đi được, chiều chị bận.
Agent: [send_message zalo] Đã gửi.
"""

print("=== Trích memory ===")
for m in ms.extract_from_run(llm, TRANSCRIPT, run_id="run_001"):
    print(f"  [{m.confidence}] {m.subject}: {m.fact}")

print("\n=== Truy hồi cho phiên mới ===")
for line in ms.retrieve("soạn tin nhắn cho chị Lan", subject="C001"):
    print(f"  • {line}")

print("\n=== Cập nhật khi mâu thuẫn ===")
rows = ms.active("C001")
if rows:
    old_id = rows[0][0]
    ms.supersede(old_id, Memory(subject="C001",
                                fact="Khách đã đồng ý nhận cuộc gọi vào buổi sáng (cập nhật 09/2026)",
                                confidence="HIGH", evidence="nhân viên xác nhận trực tiếp",
                                run_id="run_002"))
print("Memory đang hiệu lực:")
for r in ms.active("C001"):
    print(f"  {r[2]}")

print("\n" + llm.usage.report())
```

---

## 4. Bài tập

**Bài 1 — Chống nhớ sai.** Cho transcript chứa dữ liệu biến động (số buổi còn lại). Kiểm tra: extractor có nhớ nhầm không? Nếu có → siết prompt và đo lại.

**Bài 2 — Tác động lên chất lượng.** Chạy 10 nhiệm vụ với và không có memory retrieval. Đo: agent có dùng đúng kênh liên hệ khách ưa thích không? Có bớt hỏi lại nhân viên không?

**Bài 3 — Dọn memory.** Viết `prune()` xoá memory > 12 tháng chưa dùng lại, và memory bị mâu thuẫn ≥ 2 lần. Chạy thử trên dữ liệu giả.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 59 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Phân biệt rõ 4 loại bộ nhớ, dùng đúng chỗ
- [ ] Không nhớ dữ liệu biến động (chứng minh bằng test)
- [ ] Memory có nguồn gốc (run_id, evidence, confidence)
- [ ] Cập nhật memory mâu thuẫn, giữ lịch sử
- [ ] Quiz ≥ 80%
