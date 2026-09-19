# NGÀY 83 — Opportunity scoring

> Phase 6 · 20' thiết kế — 100' code + hiệu chuẩn

## 🎯 Mục tiêu

Xếp hạng cơ hội theo **giá trị kỳ vọng**, không chỉ theo giá trị tuyệt đối — để nhân viên làm việc có giá trị nhất trước.

---

## 1. Lý thuyết (20 phút)

### 1.1 Giá trị kỳ vọng, không phải giá trị tuyệt đối

```
Cơ hội A: 10.000.000đ × xác suất thành công 10% = 1.000.000đ
Cơ hội B:  3.000.000đ × xác suất thành công 60% = 1.800.000đ
                                                   ↑ nên làm B trước
```

Nhân viên chỉ duyệt được 30 tin/ngày. Xếp sai thứ tự = lãng phí thời gian quý nhất.

### 1.2 Các yếu tố ảnh hưởng xác suất

| Yếu tố | Tăng xác suất | Giảm xác suất |
|---|---|---|
| Thời gian vắng mặt | 90–150 ngày | > 300 ngày |
| Số buổi còn lại | nhiều | rất ít (1 buổi) |
| Deadline (sắp hết hạn) | có | không |
| Lịch sử chi tiêu | cao (khách trung thành) | thấp |
| Số lần đã liên hệ | 0–1 | ≥ 3 (đã phớt lờ) |
| Ghi chú tiêu cực | — | từng phàn nàn |
| Tần suất đến trước đây | đều đặn | thất thường |

### 1.3 Bắt đầu bằng rule, chuyển sang ML sau

v1: công thức có trọng số do bạn đặt, **hiệu chuẩn bằng dữ liệu thật**.
Sau 3–6 tháng, khi có ≥ 500 kết quả thật (gửi → có quay lại hay không), thay bằng mô hình học máy.

> Đừng dùng ML ngày đầu: chưa có nhãn, và rule minh bạch hơn khi thuyết phục khách hàng.

### 1.4 Hiệu chuẩn

Điểm 0.7 phải có nghĩa là "khoảng 70% sẽ quay lại". Nếu thực tế chỉ 30%, điểm của bạn **vô nghĩa**. Đo bằng biểu đồ hiệu chuẩn sau khi có dữ liệu thật.

---

## 2. Code (100 phút)

`backend/app/services/scoring.py`:

```python
"""Chấm điểm và xếp hạng cơ hội — CODE, không LLM."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from ..models import OppType


@dataclass
class ScoreWeights:
    """Trọng số ban đầu — hiệu chuẩn lại khi có dữ liệu thật."""
    base_by_type: dict = None
    absence_sweet_spot: tuple = (60, 180)
    max_absence: int = 365
    loyal_ltv_threshold: int = 20_000_000
    min_sessions_bonus: int = 2

    def __post_init__(self):
        if self.base_by_type is None:
            self.base_by_type = {
                OppType.EXPIRING_SOON: 0.55,      # có deadline -> dễ thuyết phục
                OppType.OVERDUE_REVISIT: 0.35,
                OppType.UNUSED_PACKAGE: 0.40,
                OppType.LOST_BOOKING: 0.30,
                OppType.HIGH_INTENT_LEAD: 0.25,
            }


@dataclass
class OpportunityScore:
    probability: float          # 0-1, xác suất ước tính khách phản hồi tích cực
    expected_value_vnd: int
    priority: int               # 1 (cao nhất) - 5
    factors: list[str]          # giải thích được -> dùng cho Ngày 84


def score_opportunity(*, opp_type: OppType, estimated_value_vnd: int,
                      reason_data: dict, contact_count: int = 0,
                      weights: ScoreWeights | None = None) -> OpportunityScore:
    w = weights or ScoreWeights()
    p = w.base_by_type.get(opp_type, 0.3)
    factors: list[str] = [f"cơ sở theo loại {opp_type.value}: {p:.0%}"]

    # --- thời gian vắng mặt ---
    absent = reason_data.get("vang_mat_ngay", 0)
    lo, hi = w.absence_sweet_spot
    if lo <= absent <= hi:
        p += 0.15; factors.append(f"vắng {absent} ngày — trong khoảng dễ quay lại (+15%)")
    elif absent > w.max_absence:
        p -= 0.20; factors.append(f"vắng {absent} ngày — có thể đã rời bỏ (−20%)")
    elif absent < 30:
        p -= 0.10; factors.append(f"mới đến {absent} ngày trước — chưa cần nhắc (−10%)")

    # --- deadline ---
    days_left = reason_data.get("con_lai_ngay")
    if days_left is not None and 0 < days_left <= 30:
        bump = 0.20 if days_left <= 14 else 0.10
        p += bump; factors.append(f"hết hạn sau {days_left} ngày — tạo tính cấp bách (+{bump:.0%})")

    # --- số buổi còn lại ---
    remaining = reason_data.get("buoi_con_lai", 0)
    if remaining >= w.min_sessions_bonus:
        p += 0.08; factors.append(f"còn {remaining} buổi — đủ để khách thấy đáng quay lại (+8%)")
    elif remaining == 1:
        p -= 0.05; factors.append("chỉ còn 1 buổi — động lực thấp (−5%)")

    # --- khách trung thành ---
    ltv = reason_data.get("lifetime_value", 0)
    if ltv >= w.loyal_ltv_threshold:
        p += 0.12; factors.append(f"khách thân thiết (đã chi {ltv:,}đ) (+12%)")

    # --- đã liên hệ nhiều lần ---
    if contact_count >= 3:
        p -= 0.25; factors.append(f"đã liên hệ {contact_count} lần chưa phản hồi (−25%)")
    elif contact_count == 2:
        p -= 0.10; factors.append("đã liên hệ 2 lần (−10%)")

    # --- ghi chú tiêu cực ---
    note = (reason_data.get("ghi_chu") or "").lower()
    if any(k in note for k in ("phàn nàn", "khiếu nại", "không hài lòng", "chờ lâu")):
        p -= 0.15; factors.append("từng phàn nàn — cần cách tiếp cận thận trọng (−15%)")

    p = max(0.05, min(p, 0.95))
    ev = int(estimated_value_vnd * p)
    priority = (1 if ev >= 3_000_000 else 2 if ev >= 1_500_000 else
                3 if ev >= 700_000 else 4 if ev >= 300_000 else 5)
    return OpportunityScore(round(p, 3), ev, priority, factors)


def rank(opportunities: list[dict]) -> list[dict]:
    """Xếp hạng theo giá trị kỳ vọng, không theo giá trị tuyệt đối."""
    for o in opportunities:
        s = score_opportunity(
            opp_type=o["opp_type"], estimated_value_vnd=o["estimated_value_vnd"],
            reason_data=json.loads(o["reason_data"]) if isinstance(o["reason_data"], str)
            else o["reason_data"],
            contact_count=o.get("contact_count", 0))
        o.update(probability=s.probability, expected_value_vnd=s.expected_value_vnd,
                 priority=s.priority, factors=s.factors)
    return sorted(opportunities, key=lambda x: -x["expected_value_vnd"])


def calibration_report(results: list[tuple[float, bool]], bins: int = 5) -> None:
    """results: [(điểm dự đoán, thực tế có phản hồi tích cực không)]"""
    import collections
    buckets = collections.defaultdict(list)
    for p, actual in results:
        buckets[min(int(p * bins), bins - 1)].append(actual)
    print(f"\n{'khoảng điểm':<16}{'n':>6}{'dự đoán':>10}{'thực tế':>10}{'lệch':>9}")
    print("-" * 52)
    for b in sorted(buckets):
        vals = buckets[b]
        pred = (b + 0.5) / bins
        actual = sum(vals) / len(vals)
        flag = " ⚠" if abs(pred - actual) > 0.15 else ""
        print(f"{b/bins:.1f}-{(b+1)/bins:.1f}{'':<8}{len(vals):>6}{pred:>10.0%}"
              f"{actual:>10.0%}{actual-pred:>+9.0%}{flag}")
    print("\nĐiểm được hiệu chuẩn tốt khi dự đoán ≈ thực tế ở mọi khoảng.")
```

---

## 3. Việc phải làm

1. Chạy scoring trên toàn bộ cơ hội từ Ngày 82. In top 20 theo **giá trị kỳ vọng**.
2. So sánh: thứ tự theo giá trị tuyệt đối vs theo giá trị kỳ vọng — khác nhau thế nào? Ghi lại 3 trường hợp đổi hạng mạnh nhất.
3. Với 20 cơ hội hàng đầu, tự đánh giá bằng trực giác: bạn có đồng ý với thứ tự không? Nếu không → điều chỉnh trọng số.
4. Viết `backend/tests/test_scoring.py` với ≥ 6 test cho các yếu tố.

---

## 4. PASS/FAIL

- [ ] Điểm nằm trong [0.05, 0.95], không bao giờ 0 hoặc 1
- [ ] Xếp hạng theo giá trị kỳ vọng, không theo giá trị tuyệt đối
- [ ] `factors` giải thích được **mọi** điều chỉnh điểm
- [ ] Khách vắng > 365 ngày bị hạ điểm
- [ ] Khách đã liên hệ ≥ 3 lần bị hạ điểm mạnh
- [ ] Có hàm `calibration_report` sẵn sàng cho dữ liệu thật
- [ ] ≥ 6 test pass

---

## 5. Quiz + commit

```powershell
python quiz\quiz.py --day 83 ; python quiz\quiz.py --review
git add . ; git commit -m "day 83: opportunity scoring + expected value ranking"
```
