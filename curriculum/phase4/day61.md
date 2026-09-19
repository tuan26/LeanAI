# NGÀY 61 — Human-in-the-loop

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note
> ⭐ Ngày quan trọng nhất về mặt **sản phẩm** trong Phase 4.

## 🎯 Mục tiêu

Mọi hành động có hậu quả đều đi qua **Approve / Edit / Reject** — và thiết kế sao cho người duyệt thật sự đọc, không bấm cho xong.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Ba mức tự động

```
MỨC 1 — ĐỀ XUẤT  : AI soạn, người bấm gửi                  ← bắt đầu ở đây
MỨC 2 — DUYỆT LÔ : AI soạn N tin, người duyệt hàng loạt
MỨC 3 — TỰ ĐỘNG  : AI tự gửi, người xem lại sau            ← chỉ khi đã có số liệu
```

> **Luật:** không lên mức cao hơn cho đến khi có ≥ 200 mẫu ở mức hiện tại với tỉ lệ người sửa < 10%.

Đây không phải sự thận trọng thừa. Một tin nhắn sai gửi cho 500 khách là sự cố thương hiệu không rút lại được.

### 1.2 Phân loại hành động

| Loại | Ví dụ | Cần duyệt |
|---|---|---|
| Đọc | tra cứu khách, xem lịch | ❌ |
| Ghi nội bộ | ghi chú, đánh dấu | ❌ (nhưng ghi log) |
| **Ghi ra ngoài** | gửi tin, email | ✅ luôn luôn |
| **Tài chính** | hoàn tiền, đổi gói | ✅ + quyền cao hơn |
| **Không hoàn tác** | xoá dữ liệu | ✅ + xác nhận 2 lần |

### 1.3 Thiết kế màn hình duyệt — chống "bấm cho xong"

Người duyệt 50 tin liên tiếp sẽ bấm Approve theo quán tính. Chống lại bằng:

```
1. Hiện ĐÚNG NGUYÊN VĂN sẽ gửi, không phải tóm tắt
2. Hiện VÌ SAO: dữ liệu nào dẫn đến đề xuất này
3. Đánh dấu ĐỎ những điểm cần chú ý (khách từng khiếu nại, giá trị lớn)
4. Bắt buộc nhập lý do khi Reject → thu được dữ liệu cải tiến
5. Sắp xếp theo rủi ro: ca khó lên đầu, lúc người còn tỉnh táo
```

### 1.4 Reject là dữ liệu quý nhất

Mỗi lần người sửa hoặc từ chối → bạn có một mẫu "AI làm sai". Thu thập đủ 100 mẫu này, bạn có bộ few-shot và bộ eval tốt hơn mọi thứ tự nghĩ ra.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Building effective agents (phần human oversight) | https://www.anthropic.com/research/building-effective-agents |
| Google PAIR — Human-AI guidebook | https://pair.withgoogle.com/guidebook/ |

---

## 3. Thực hành (80 phút)

`leanai_core/approval.py`:

```python
"""Human-in-the-loop: approve / edit / reject có ghi nhận."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

DB_PATH = Path("data/approvals.db")


class Decision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    run_id: str
    tenant_id: str
    tool: str
    args: dict
    preview: str                       # ĐÚNG nội dung sẽ thực thi
    rationale: str                     # vì sao AI đề xuất
    evidence: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    estimated_value: int = 0
    id: int = 0


class ApprovalQueue:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS approvals(
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, tenant_id TEXT,
            tool TEXT, args TEXT, preview TEXT, rationale TEXT, evidence TEXT,
            risk_flags TEXT, estimated_value INT, decision TEXT, final_content TEXT,
            reject_reason TEXT, reviewer TEXT, created_at TEXT, decided_at TEXT)""")
        self.db.commit()

    def submit(self, req: ApprovalRequest) -> int:
        cur = self.db.execute(
            "INSERT INTO approvals(run_id,tenant_id,tool,args,preview,rationale,"
            "evidence,risk_flags,estimated_value,decision,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (req.run_id, req.tenant_id, req.tool,
             json.dumps(req.args, ensure_ascii=False), req.preview, req.rationale,
             json.dumps(req.evidence, ensure_ascii=False),
             json.dumps(req.risk_flags, ensure_ascii=False), req.estimated_value,
             Decision.PENDING.value, datetime.now(timezone.utc).isoformat()))
        self.db.commit()
        return cur.lastrowid

    def pending(self, tenant_id: str, order_by_risk: bool = True) -> list[dict]:
        rows = self.db.execute(
            "SELECT id,run_id,tool,args,preview,rationale,evidence,risk_flags,"
            "estimated_value,created_at FROM approvals "
            "WHERE tenant_id=? AND decision='pending'", (tenant_id,)).fetchall()
        items = [{"id": r[0], "run_id": r[1], "tool": r[2], "args": json.loads(r[3]),
                  "preview": r[4], "rationale": r[5], "evidence": json.loads(r[6]),
                  "risk_flags": json.loads(r[7]), "value": r[8], "created_at": r[9]}
                 for r in rows]
        if order_by_risk:
            items.sort(key=lambda x: (-len(x["risk_flags"]), -x["value"]))
        return items

    def decide(self, approval_id: int, decision: Decision, *, reviewer: str,
               final_content: str = "", reject_reason: str = "") -> None:
        self.db.execute(
            "UPDATE approvals SET decision=?, final_content=?, reject_reason=?, "
            "reviewer=?, decided_at=? WHERE id=?",
            (decision.value, final_content, reject_reason, reviewer,
             datetime.now(timezone.utc).isoformat(), approval_id))
        self.db.commit()

    def stats(self, tenant_id: str) -> dict:
        rows = self.db.execute(
            "SELECT decision, COUNT(*) FROM approvals WHERE tenant_id=? GROUP BY decision",
            (tenant_id,)).fetchall()
        d = dict(rows)
        total = sum(d.values()) or 1
        decided = total - d.get("pending", 0) or 1
        return {"tổng": total, **d,
                "tỉ lệ duyệt thẳng": round(d.get("approved", 0) / decided, 3),
                "tỉ lệ người sửa": round((d.get("edited", 0) + d.get("rejected", 0)) / decided, 3)}

    def learning_samples(self, tenant_id: str) -> list[dict]:
        """Mẫu AI làm sai — dùng làm few-shot và eval."""
        rows = self.db.execute(
            "SELECT preview, final_content, reject_reason, decision FROM approvals "
            "WHERE tenant_id=? AND decision IN ('edited','rejected')", (tenant_id,)).fetchall()
        return [{"ai_draft": r[0], "human_version": r[1],
                 "reason": r[2], "decision": r[3]} for r in rows]


def risk_flags_for_message(customer: dict, message: str) -> list[str]:
    flags = []
    if customer.get("ghi_chu"):
        flags.append(f"⚠ Ghi chú CRM: {customer['ghi_chu']}")
    if customer.get("gia_tri_chua_dung", 0) > 5_000_000:
        flags.append(f"💰 Giá trị lớn: {customer['gia_tri_chua_dung']:,}đ")
    if customer.get("vang_mat_ngay", 0) > 180:
        flags.append("🕐 Vắng rất lâu — có thể đã dùng dịch vụ nơi khác")
    if any(w in message.lower() for w in ("khuyến mãi", "giảm giá", "miễn phí", "tặng")):
        flags.append("🚨 Tin nhắn hứa ưu đãi — kiểm tra kỹ")
    return flags
```

`exercises/day61/review_cli.py`:

```python
"""Màn hình duyệt CLI — tiền thân giao diện Ngày 87."""
from leanai_core.approval import ApprovalQueue, Decision, ApprovalRequest, risk_flags_for_message

q = ApprovalQueue()
T = "clinic_001"

# --- nạp dữ liệu mẫu (thực tế do agent sinh) ---
if not q.pending(T):
    samples = [
        (dict(ten="Nguyễn Thị Lan", ghi_chu="phàn nàn chờ lâu 03/2026",
              gia_tri_chua_dung=4_800_000, vang_mat_ngay=112),
         "Chị Lan ơi, gói trị liệu của chị còn 4 buổi và hết hạn sau 25 ngày ạ. "
         "Em giữ giúp chị khung giờ sáng ít khách nhé. Chị sắp xếp được hôm nào ạ?",
         "Vắng 112 ngày, còn 4/10 buổi trị giá 4.800.000đ, hết hạn sau 25 ngày"),
        (dict(ten="Trần Văn Bình", ghi_chu="", gia_tri_chua_dung=8_000_000, vang_mat_ngay=9),
         "Anh Bình ơi, em tặng anh khuyến mãi giảm giá 50% cho buổi tiếp theo!",
         "Mới mua gói 20 buổi, chưa dùng buổi nào"),
    ]
    for cust, msg, why in samples:
        q.submit(ApprovalRequest(
            run_id="run_demo", tenant_id=T, tool="send_message",
            args={"customer_id": "C00X", "channel": "zalo", "message": msg},
            preview=msg, rationale=why,
            evidence=[f"vắng {cust['vang_mat_ngay']} ngày",
                      f"giá trị chưa dùng {cust['gia_tri_chua_dung']:,}đ"],
            risk_flags=risk_flags_for_message(cust, msg),
            estimated_value=cust["gia_tri_chua_dung"]))

for item in q.pending(T):
    print("\n" + "=" * 74)
    print(f"#{item['id']}  {item['tool']}  |  giá trị ước tính {item['value']:,}đ")
    print(f"VÌ SAO: {item['rationale']}")
    print(f"BẰNG CHỨNG: {', '.join(item['evidence'])}")
    for f in item["risk_flags"]:
        print(f"  {f}")
    print("-" * 74)
    print("NỘI DUNG SẼ GỬI (nguyên văn):")
    print(item["preview"])
    print("-" * 74)
    choice = input("[a]pprove  [e]dit  [r]eject  [s]kip: ").strip().lower()
    if choice == "a":
        q.decide(item["id"], Decision.APPROVED, reviewer="tuan",
                 final_content=item["preview"])
    elif choice == "e":
        new = input("Nội dung sửa: ")
        q.decide(item["id"], Decision.EDITED, reviewer="tuan", final_content=new)
    elif choice == "r":
        reason = input("Lý do từ chối (BẮT BUỘC): ")
        while not reason.strip():
            reason = input("Phải nhập lý do: ")
        q.decide(item["id"], Decision.REJECTED, reviewer="tuan", reject_reason=reason)

print("\n=== THỐNG KÊ ===")
for k, v in q.stats(T).items():
    print(f"  {k}: {v}")
print("\n=== MẪU HỌC ĐƯỢC (AI làm sai) ===")
for s in q.learning_samples(T):
    print(f"  [{s['decision']}] {s['reason'] or 'người sửa lại'}")
```

---

## 4. Bài tập

**Bài 1 — Tích hợp agent.** Sửa `Agent` để khi gọi tool có `requires_approval=True` thì **dừng**, chuyển state sang `WAITING_APPROVAL`, tạo `ApprovalRequest`. Sau khi duyệt thì `resume()`.

**Bài 2 — Đo chất lượng người duyệt.** Cho 20 đề xuất trong đó **3 cái sai rõ ràng** (số liệu sai, hứa ưu đãi không có). Tự duyệt nhanh như khi bận. Bạn có bắt được cả 3 không? Nếu không → cải tiến màn hình duyệt và thử lại.

**Bài 3 — Biến reject thành cải tiến.** Thu thập ≥ 10 mẫu edited/rejected. Dùng chúng làm few-shot (Ngày 23) cho prompt soạn tin. Đo tỉ lệ người sửa trước/sau.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 61 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Mọi tool `read_only=False` đều đi qua hàng chờ duyệt
- [ ] Màn hình duyệt hiện: nguyên văn + vì sao + bằng chứng + cờ rủi ro
- [ ] Reject **bắt buộc** nhập lý do
- [ ] Sắp xếp theo rủi ro, ca khó lên đầu
- [ ] Agent dừng và khôi phục đúng quanh điểm duyệt
- [ ] Có ≥ 10 mẫu học được từ edit/reject
- [ ] Quiz ≥ 80%
