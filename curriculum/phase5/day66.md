# NGÀY 66 — Evaluation: xây dataset

> Phase 5 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Bộ eval **50 case** cho CareDesk-AI — tài sản quan trọng nhất của Phase 5.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Không có eval = không có sản phẩm

```
Không eval:  "tôi thấy nó chạy khá tốt"       → không sửa được, không bán được
Có eval:     "precision 0.87, recall 0.79 trên 50 case, thất bại ở nhóm X"
```

Eval là cách duy nhất để: biết cải tiến có hiệu quả, biết khi nào regression, và **trả lời khách hàng khi họ hỏi "AI này chính xác bao nhiêu phần trăm?"**

### 1.2 Bốn tầng eval

| Tầng | Đo gì | Ví dụ |
|---|---|---|
| **Unit** | một bước | prompt phân loại có ra đúng enum không |
| **Component** | một module | RAG recall@5 (Ngày 50) |
| **End-to-end** | cả luồng | từ dữ liệu khách → tin nhắn cuối |
| **Regression** | không tệ đi | chạy lại toàn bộ sau mỗi thay đổi |

### 1.3 Nguyên tắc xây dataset

```
1. Lấy từ THỰC TẾ, đừng bịa hết        — dữ liệu thật có những ca bạn không nghĩ ra
2. Cân bằng: dễ / trung bình / khó      — toàn ca dễ = chỉ số đẹp giả
3. Có ca KHÔNG NÊN hành động            — đo false positive
4. Có ca biên và ca mâu thuẫn
5. Nhãn do NGƯỜI gán                    — nhãn do AI gán chỉ đo "AI giống AI"
6. Đóng băng test set                   — sửa test set để đạt chỉ số là tự lừa
```

### 1.4 Dataset cho CareDesk-AI

| Nhóm | Số ca | Đo gì |
|---|---|---|
| Có cơ hội rõ ràng | 15 | phát hiện đúng loại |
| Không có cơ hội | 10 | **không** tạo cơ hội giả (false positive) |
| Ca biên | 10 | vừa hết hạn, vừa mua, vắng ranh giới |
| Không nên liên hệ | 8 | khiếu nại mở, khách chặn, vừa gửi tin |
| Dữ liệu thiếu/bẩn | 7 | thiếu ngày mua, số âm, ngày tương lai |

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Create strong empirical evaluations | https://docs.anthropic.com/en/docs/test-and-evaluate/develop-tests |
| Hamel Husain — Your AI product needs evals | https://hamel.dev/blog/posts/evals/ |

---

## 3. Thực hành (80 phút)

`templates/schemas/eval-case.json`:

```jsonc
{
  "id": "EV-001",
  "group": "clear_opportunity",
  "input": {
    "customer": {
      "customer_id": "C001", "ten": "Nguyễn Thị Lan",
      "goi": "Trị liệu da mặt", "tong_buoi": 10, "da_dung": 6,
      "gia": 12000000, "ngay_mua": "2026-04-12", "han_thang": 6,
      "lan_cuoi": "2026-05-28", "ghi_chu": "phàn nàn chờ lâu 03/2026",
      "khieu_nai_mo": false, "opt_out": false
    },
    "today": "2026-09-19"
  },
  "expected": {
    "has_opportunity": true,
    "opportunity_type": "OVERDUE_REVISIT",
    "should_contact": true,
    "channel": "zalo",
    "estimated_value_vnd": 4800000,
    "must_mention": ["4 buổi", "hết hạn"],
    "must_not_mention": ["khuyến mãi", "giảm giá"],
    "needs_human_review": true
  },
  "difficulty": "easy",
  "note": "Ca chuẩn: vắng 112 ngày, còn 4 buổi, sắp hết hạn"
}
```

`leanai_core/eval_dataset.py`:

```python
"""Quản lý bộ eval: nạp, kiểm tra tính hợp lệ, thống kê."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EvalCase:
    id: str
    group: str
    input: dict
    expected: dict
    difficulty: str = "medium"
    note: str = ""


@dataclass
class EvalSet:
    cases: list[EvalCase] = field(default_factory=list)

    @classmethod
    def load(cls, path: str) -> "EvalSet":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([EvalCase(**c) for c in raw])

    def save(self, path: str) -> None:
        Path(path).write_text(
            json.dumps([c.__dict__ for c in self.cases], ensure_ascii=False, indent=2),
            encoding="utf-8")

    def validate(self) -> list[str]:
        errs = []
        ids = [c.id for c in self.cases]
        dupes = [i for i, n in Counter(ids).items() if n > 1]
        if dupes:
            errs.append(f"id trùng: {dupes}")
        for c in self.cases:
            if "customer" not in c.input:
                errs.append(f"{c.id}: thiếu input.customer")
            if "has_opportunity" not in c.expected:
                errs.append(f"{c.id}: thiếu expected.has_opportunity")
            if c.expected.get("has_opportunity") and not c.expected.get("opportunity_type"):
                errs.append(f"{c.id}: có cơ hội nhưng thiếu opportunity_type")
        neg = sum(1 for c in self.cases if not c.expected.get("has_opportunity"))
        if neg / max(len(self.cases), 1) < 0.25:
            errs.append(f"chỉ {neg}/{len(self.cases)} ca âm — cần ≥25% để đo false positive")
        return errs

    def stats(self) -> dict:
        return {
            "tổng": len(self.cases),
            "theo nhóm": dict(Counter(c.group for c in self.cases)),
            "theo độ khó": dict(Counter(c.difficulty for c in self.cases)),
            "ca có cơ hội": sum(1 for c in self.cases if c.expected.get("has_opportunity")),
            "ca không nên liên hệ": sum(1 for c in self.cases
                                        if not c.expected.get("should_contact")),
        }

    def split(self, dev_ratio: float = 0.4) -> tuple["EvalSet", "EvalSet"]:
        """Dev set để thử nghiệm, test set ĐÓNG BĂNG để đo thật."""
        n = int(len(self.cases) * dev_ratio)
        return EvalSet(self.cases[:n]), EvalSet(self.cases[n:])
```

`exercises/day66/build_dataset.py` — sinh khung 50 case để bạn điền tay:

```python
"""Sinh khung 50 case — bạn PHẢI tự gán nhãn expected."""
import json
from datetime import date, timedelta
from pathlib import Path

TODAY = date(2026, 9, 19)

GROUPS = {
 "clear_opportunity": 15, "no_opportunity": 10, "edge_case": 10,
 "should_not_contact": 8, "dirty_data": 7,
}

TEMPLATES = {
 "clear_opportunity": lambda i: dict(
    tong_buoi=10, da_dung=6, gia=12_000_000, han_thang=6,
    ngay_mua=str(TODAY - timedelta(days=160)), lan_cuoi=str(TODAY - timedelta(days=112))),
 "no_opportunity": lambda i: dict(
    tong_buoi=10, da_dung=10, gia=12_000_000, han_thang=6,
    ngay_mua=str(TODAY - timedelta(days=100)), lan_cuoi=str(TODAY - timedelta(days=5))),
 "edge_case": lambda i: dict(
    tong_buoi=10, da_dung=9, gia=12_000_000, han_thang=6,
    ngay_mua=str(TODAY - timedelta(days=179)), lan_cuoi=str(TODAY - timedelta(days=89))),
 "should_not_contact": lambda i: dict(
    tong_buoi=10, da_dung=4, gia=12_000_000, han_thang=6,
    ngay_mua=str(TODAY - timedelta(days=150)), lan_cuoi=str(TODAY - timedelta(days=120)),
    khieu_nai_mo=(i % 2 == 0), opt_out=(i % 2 == 1)),
 "dirty_data": lambda i: dict(
    tong_buoi=10, da_dung=[12, -1, 0][i % 3], gia=12_000_000, han_thang=6,
    ngay_mua=["", str(TODAY + timedelta(days=30)), str(TODAY - timedelta(days=400))][i % 3],
    lan_cuoi=""),
}

cases, n = [], 0
for group, count in GROUPS.items():
    for i in range(count):
        n += 1
        cases.append({
            "id": f"EV-{n:03d}", "group": group,
            "input": {"customer": {"customer_id": f"C{n:03d}",
                                   "ten": f"Khách {n}", "goi": "Trị liệu da mặt",
                                   "ghi_chu": "", "khieu_nai_mo": False, "opt_out": False,
                                   **TEMPLATES[group](i)},
                      "today": str(TODAY)},
            "expected": {"has_opportunity": None, "opportunity_type": None,
                         "should_contact": None, "channel": None,
                         "estimated_value_vnd": None, "must_mention": [],
                         "must_not_mention": ["khuyến mãi", "giảm giá"],
                         "needs_human_review": True},
            "difficulty": "medium", "note": "TODO: gán nhãn tay"})

Path("data").mkdir(exist_ok=True)
Path("data/eval-50-draft.json").write_text(
    json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Đã sinh {len(cases)} khung case -> data/eval-50-draft.json")
print("BƯỚC TIẾP THEO: mở file và tự gán nhãn 'expected'. Đây là việc KHÔNG được nhờ AI làm.")
```

---

## 4. Bài tập

**Bài 1 — Gán nhãn 50 case.** Điền `expected` cho toàn bộ. Tự tay, không dùng AI. Ghi thời gian bạn mất — con số này dùng để báo giá dự án sau này.

**Bài 2 — Kiểm tra dataset.** Chạy `validate()` và `stats()`. Sửa cho đến khi không còn lỗi và tỉ lệ ca âm ≥ 25%.

**Bài 3 — Chia dev/test.** Chia 40/60. **Đóng băng test set**: copy vào `data/eval-test-FROZEN.json`, chỉ chạy khi cần đo thật, không dùng để thử nghiệm.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 66 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] 50 case có nhãn do **bạn** gán
- [ ] ≥ 25% ca âm (không có cơ hội / không nên liên hệ)
- [ ] `validate()` không còn lỗi
- [ ] Có dev set và test set đóng băng riêng biệt
- [ ] Ghi được thời gian gán nhãn thực tế
- [ ] Quiz ≥ 80%
