# NGÀY 89 — Evaluation 100 scenarios

> Phase 6 · Cả ngày. Đây là **số liệu bạn sẽ đưa lên sân khấu ngày mai**.

## 🎯 Mục tiêu

Đánh giá toàn hệ thống trên 100 kịch bản khách hàng, ra được 8 chỉ số có thể đưa cho khách hàng xem.

---

## 1. Bộ 100 kịch bản

Mở rộng bộ 50 case Ngày 66 lên 100:

| Nhóm | Số ca | Kiểm tra |
|---|---|---|
| Cơ hội rõ ràng | 25 | phát hiện đúng loại, giá trị đúng |
| Không có cơ hội | 20 | **không** tạo cơ hội giả |
| Ca biên | 20 | ranh giới ngày/số buổi/hạn dùng |
| Không được liên hệ | 15 | opt-out, khiếu nại, vừa gửi tin |
| Dữ liệu bẩn | 10 | thiếu trường, số âm, ngày tương lai |
| Đa tenant | 10 | không rò rỉ chéo |

---

## 2. Script đánh giá

`projects/capstone-caredesk-ai/evaluate.py`:

```python
"""Đánh giá end-to-end CareDesk-AI trên 100 kịch bản."""
from __future__ import annotations

import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from app.services.detector import detect_all, DetectionRules
from app.services.scoring import score_opportunity
from app.services.explainer import explain, verify_no_ghost_numbers
from app.services.drafter import draft_message
from app.services.guards import check_business_rules
from leanai_core.llm import LLMClient

llm = LLMClient()


def evaluate(cases: list[dict]) -> dict:
    tp = fp = fn = tn = 0
    type_correct = value_correct = 0
    msg_number_errors = msg_guardrail_pass = explain_fallback = 0
    latencies, costs = [], []
    by_group = defaultdict(lambda: {"n": 0, "ok": 0})
    failures = []

    for c in cases:
        t0 = time.time()
        cost_before = llm.usage.cost
        cust = c["input"]["customer"]
        exp = c["expected"]

        # --- 1. phát hiện ---
        found = detect_for_case(cust, c["input"]["today"])
        has_opp = bool(found)

        if has_opp and exp["has_opportunity"]:
            tp += 1
            o = found[0]
            if o.opp_type.value == exp.get("opportunity_type"):
                type_correct += 1
            if exp.get("estimated_value_vnd") and \
                    abs(o.estimated_value_vnd - exp["estimated_value_vnd"]) <= 1000:
                value_correct += 1
        elif has_opp and not exp["has_opportunity"]:
            fp += 1
            failures.append({"id": c["id"], "loại": "false positive",
                             "chi tiết": f"tạo cơ hội {found[0].opp_type.value} không nên có"})
        elif not has_opp and exp["has_opportunity"]:
            fn += 1
            failures.append({"id": c["id"], "loại": "false negative",
                             "chi tiết": f"bỏ sót {exp.get('opportunity_type')}"})
        else:
            tn += 1

        # --- 2. giải thích + soạn tin (chỉ khi có cơ hội) ---
        if has_opp and exp.get("should_contact"):
            o = found[0]
            s = score_opportunity(opp_type=o.opp_type,
                                  estimated_value_vnd=o.estimated_value_vnd,
                                  reason_data=o.reason_data)
            ex = explain(o.reason_data, probability=s.probability,
                         expected_value=s.expected_value_vnd, factors=s.factors)
            if ex.generated_by == "template":
                explain_fallback += 1

            d = draft_message(o.reason_data, opp_type=o.opp_type, channel="zalo",
                              explanation=ex.text)
            ghost = verify_no_ghost_numbers(d.text, o.reason_data)
            if ghost:
                msg_number_errors += 1
                failures.append({"id": c["id"], "loại": "số bịa trong tin nhắn",
                                 "chi tiết": str(ghost)})
            if not d.violations:
                msg_guardrail_pass += 1

            for must in exp.get("must_mention", []):
                if must.lower() not in d.text.lower():
                    failures.append({"id": c["id"], "loại": "thiếu nội dung bắt buộc",
                                     "chi tiết": must})
            for banned in exp.get("must_not_mention", []):
                if banned.lower() in d.text.lower():
                    failures.append({"id": c["id"], "loại": "chứa từ cấm",
                                     "chi tiết": banned})

        latencies.append(time.time() - t0)
        costs.append(llm.usage.cost - cost_before)
        g = by_group[c["group"]]
        g["n"] += 1
        g["ok"] += int(has_opp == exp["has_opportunity"])

    n = len(cases)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    latencies.sort()
    return {
        "n_cases": n,
        "precision": round(prec, 3), "recall": round(rec, 3),
        "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0,
        "confusion": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "type_accuracy": round(type_correct / max(tp, 1), 3),
        "value_accuracy": round(value_correct / max(tp, 1), 3),
        "message_number_errors": msg_number_errors,
        "message_guardrail_pass_rate": round(msg_guardrail_pass / max(tp, 1), 3),
        "explanation_fallback_rate": round(explain_fallback / max(tp, 1), 3),
        "latency_p50": round(statistics.median(latencies), 2),
        "latency_p95": round(latencies[int(n * 0.95) - 1], 2),
        "cost_per_case_usd": round(sum(costs) / n, 5),
        "cost_per_case_vnd": int(sum(costs) / n * 25000),
        "by_group": {k: {**v, "accuracy": round(v["ok"] / v["n"], 3)}
                     for k, v in by_group.items()},
        "failures": failures,
    }


if __name__ == "__main__":
    cases = json.loads(Path("data/eval-100.json").read_text(encoding="utf-8"))
    r = evaluate(cases)

    print("=" * 66)
    print("KẾT QUẢ ĐÁNH GIÁ CareDesk-AI")
    print("=" * 66)
    targets = {"precision": 0.85, "recall": 0.75, "type_accuracy": 0.90,
               "value_accuracy": 0.98, "message_guardrail_pass_rate": 0.85}
    for k, t in targets.items():
        v = r[k]
        print(f"{k:<30}{v:>8.3f}  mục tiêu ≥{t}  {'✓' if v >= t else '✗'}")
    print(f"{'số liệu sai trong tin nhắn':<30}{r['message_number_errors']:>8}"
          f"  mục tiêu 0  {'✓' if r['message_number_errors'] == 0 else '✗'}")
    print(f"{'latency p50 / p95':<30}{r['latency_p50']:>8.2f}s / {r['latency_p95']:.2f}s")
    print(f"{'chi phí / kịch bản':<30}{r['cost_per_case_vnd']:>8,}đ")

    print("\nĐộ chính xác theo nhóm:")
    for g, v in sorted(r["by_group"].items(), key=lambda x: x[1]["accuracy"]):
        print(f"  {g:<24}{v['accuracy']:>6.2f}  ({v['ok']}/{v['n']})"
              f"{'  ⚠' if v['accuracy'] < 0.8 else ''}")

    print(f"\n{len(r['failures'])} lỗi — theo loại:")
    for kind, cnt in Counter(f["loại"] for f in r["failures"]).most_common():
        print(f"  {kind:<32}{cnt}")
    print("\n10 lỗi đầu:")
    for f in r["failures"][:10]:
        print(f"  [{f['id']}] {f['loại']}: {f['chi tiết'][:60]}")

    Path("projects/capstone-caredesk-ai/EVAL.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nĐã lưu EVAL.json")
```

---

## 3. Báo cáo cho khách hàng

`projects/capstone-caredesk-ai/RESULTS.md`:

```markdown
# CareDesk-AI — Kết quả đánh giá

Đánh giá trên **100 kịch bản khách hàng** đại diện cho các tình huống thực tế.

## Độ chính xác
| Chỉ số | Kết quả | Ý nghĩa với phòng khám |
|---|---|---|
| Precision | 0.__ | Khi hệ thống báo có cơ hội, đúng __% |
| Recall | 0.__ | Trong các cơ hội thật, hệ thống bắt được __% |
| Độ chính xác số liệu trong tin nhắn | 100% | Không bao giờ nhắn sai số buổi/ngày hết hạn |
| Tỉ lệ báo nhầm khách không nên liên hệ | __% | |

## Hiệu năng
| Chỉ số | Kết quả |
|---|---|
| Thời gian xử lý 1 khách | __s (p50) / __s (p95) |
| Quét toàn bộ 3.000 khách | __ phút |
| Chi phí AI / phòng khám / tháng | ___đ |

## Giới hạn đã biết (nói trước với khách hàng)
- Hệ thống KHÔNG tự gửi tin — mọi tin đều cần nhân viên duyệt
- Không dự đoán được khách có quay lại hay không, chỉ xếp hạng khả năng
- Cần dữ liệu tối thiểu: ngày mua gói, số buổi, lần đến cuối
- Với khách vắng > 300 ngày, độ chính xác giảm rõ rệt
- Chưa tích hợp phần mềm đặt lịch — doanh thu thu hồi cần đánh dấu tay

## Cách chúng tôi chống AI bịa
1. Số liệu do hệ thống chèn, AI chỉ viết câu chữ
2. Mọi tin nhắn được kiểm tra tự động trước khi hiển thị
3. Nhân viên duyệt trước khi gửi
4. Mọi hành động được ghi lại đầy đủ
```

---

## 4. PASS/FAIL

- [ ] Bộ 100 kịch bản đủ 6 nhóm
- [ ] Precision ≥ 0.85, Recall ≥ 0.75
- [ ] **Số liệu sai trong tin nhắn = 0**
- [ ] Không rò rỉ tenant trên 10 ca đa tenant
- [ ] p95 latency và chi phí/kịch bản đo được
- [ ] Phân tích được ≥ 10 ca thất bại theo nguyên nhân
- [ ] `RESULTS.md` viết cho **khách hàng đọc**, không dùng thuật ngữ kỹ thuật
- [ ] Mục "Giới hạn đã biết" trung thực, không giấu

---

## 5. Quiz + commit

```powershell
python quiz\quiz.py --day 89 ; python quiz\quiz.py --exam 76 89
git add . ; git commit -m "day 89: end-to-end evaluation on 100 scenarios"
```
