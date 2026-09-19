# NGÀY 67 — Evaluation: scorer & LLM-judge

> Phase 5 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Chấm điểm tự động **đáng tin** — và biết khi nào LLM-judge nói dối.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Ba loại scorer — dùng đúng chỗ

| Loại | Dùng cho | Tin cậy | Chi phí |
|---|---|---|---|
| **Deterministic** | enum, số, boolean, regex, độ dài | 100% | 0 |
| **LLM-judge** | chất lượng văn bản, tính phù hợp | 70–90% | tốn |
| **Người** | ca tranh cãi, hiệu chuẩn judge | chuẩn vàng | rất tốn |

> **Quy tắc:** deterministic trước, LLM-judge chỉ cho phần còn lại. Đừng dùng LLM để kiểm tra `opportunity_type == "OVERDUE_REVISIT"`.

### 1.2 Chỉ số phân loại

```
                 Dự đoán CÓ    Dự đoán KHÔNG
Thực tế CÓ          TP              FN          ← bỏ sót cơ hội (mất tiền)
Thực tế KHÔNG       FP              TN          ← làm phiền khách (mất uy tín)

Precision = TP/(TP+FP)   "khi AI nói có, đúng bao nhiêu %"
Recall    = TP/(TP+FN)   "trong các cơ hội thật, AI bắt được bao nhiêu %"
F1        = trung bình điều hoà
```

**Với CareDesk-AI: precision quan trọng hơn recall.** Bỏ sót một cơ hội chỉ mất tiền tiềm năng; làm phiền nhầm khách làm hỏng quan hệ thật.

### 1.3 LLM-judge — bốn quy tắc bắt buộc

```
1. Tiêu chí CỤ THỂ, không hỏi "có tốt không"
2. Thang điểm RỜI RẠC (đúng/sai, 1-3), không thang 1-10
3. Bắt nêu LÝ DO trước khi cho điểm
4. HIỆU CHUẨN: so judge với nhãn người trên ≥ 20 ca
```

Nếu judge chỉ đồng ý với người 60% → **judge của bạn vô dụng**, phải sửa prompt trước khi tin nó.

### 1.4 Thiên lệch của LLM-judge

| Thiên lệch | Biểu hiện | Cách giảm |
|---|---|---|
| Vị trí | thích phương án đầu/cuối | đảo thứ tự, chạy 2 lần |
| Độ dài | thích câu trả lời dài | nói rõ "độ dài không phải tiêu chí" |
| Tự ưa | thích văn của chính model đó | dùng model khác làm judge |
| Nới tay | ít khi cho điểm thấp | ép nêu lỗi trước, dùng thang nhị phân |

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Grading evals | https://docs.anthropic.com/en/docs/test-and-evaluate/develop-tests |
| Judging LLM-as-a-Judge (paper) | https://arxiv.org/abs/2306.05685 |

---

## 3. Thực hành (80 phút)

`leanai_core/scorers.py`:

```python
"""Bộ chấm điểm: deterministic + LLM-judge có hiệu chuẩn."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .jsonutil import safe_json_loads
from .llm import LLMClient


@dataclass
class Score:
    name: str
    passed: bool
    detail: str = ""
    value: float = 0.0


# ---------- deterministic ----------
def score_enum(actual, expected, name="enum") -> Score:
    ok = actual == expected
    return Score(name, ok, f"{actual} (mong đợi {expected})", 1.0 if ok else 0.0)


def score_bool(actual, expected, name="bool") -> Score:
    return score_enum(bool(actual), bool(expected), name)


def score_number(actual, expected, tol: float = 0.05, name="số") -> Score:
    if actual is None or expected is None:
        return Score(name, actual == expected, f"{actual} vs {expected}")
    diff = abs(actual - expected) / max(abs(expected), 1)
    ok = diff <= tol
    return Score(name, ok, f"{actual:,} vs {expected:,} (lệch {diff:.1%})",
                 1.0 if ok else 0.0)


def score_contains(text: str, must: list[str], must_not: list[str]) -> Score:
    t = text.lower()
    missing = [m for m in must if m.lower() not in t]
    banned = [m for m in must_not if m.lower() in t]
    ok = not missing and not banned
    return Score("nội dung", ok,
                 f"thiếu {missing}; cấm {banned}" if not ok else "đủ", 1.0 if ok else 0.0)


# ---------- LLM-judge ----------
JUDGE_PROMPT = """Bạn chấm chất lượng tin nhắn chăm sóc khách hàng của spa.

<dữ_liệu_khách>
{customer}
</dữ_liệu_khách>

<tin_nhắn>
{message}
</tin_nhắn>

Kiểm tra TỪNG tiêu chí. Nêu LỖI trước, cho điểm sau. Độ dài KHÔNG phải tiêu chí.

1. chinh_xac: mọi con số trong tin nhắn có đúng với <dữ_liệu_khách> không?
2. phu_hop: có tôn trọng ghi chú CRM (kênh ưa thích, từng khiếu nại) không?
3. khong_hua_hen: KHÔNG hứa ưu đãi/giảm giá không có trong dữ liệu?
4. tu_nhien: đọc có giống người Việt viết không (không máy móc, xưng hô đúng)?
5. co_ly_do: có nêu lý do cụ thể để khách quay lại không?

Mỗi tiêu chí: PASS hoặc FAIL. Không có mức trung gian.

CHỈ JSON: {{"issues":["<lỗi cụ thể>"],
"scores":{{"chinh_xac":"PASS|FAIL","phu_hop":"PASS|FAIL","khong_hua_hen":"PASS|FAIL",
"tu_nhien":"PASS|FAIL","co_ly_do":"PASS|FAIL"}}}}"""


@dataclass
class JudgeResult:
    scores: dict[str, str] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    @property
    def passed_all(self) -> bool:
        return bool(self.scores) and all(v == "PASS" for v in self.scores.values())

    @property
    def ratio(self) -> float:
        if not self.scores:
            return 0.0
        return sum(1 for v in self.scores.values() if v == "PASS") / len(self.scores)


def judge_message(llm: LLMClient, customer: dict, message: str) -> JudgeResult:
    r = llm.complete(JUDGE_PROMPT.format(customer=customer, message=message),
                     temperature=0, max_tokens=600, tag="judge")
    d = safe_json_loads(r.text, {"scores": {}, "issues": []})
    return JudgeResult(d.get("scores", {}), d.get("issues", []))


# ---------- hiệu chuẩn judge ----------
def calibrate(llm: LLMClient, samples: list[dict]) -> dict:
    """samples: [{"customer":..., "message":..., "human_verdict": True/False}]"""
    agree = 0
    fp = fn = 0
    for s in samples:
        j = judge_message(llm, s["customer"], s["message"])
        pred = j.passed_all
        truth = s["human_verdict"]
        agree += pred == truth
        fp += pred and not truth
        fn += (not pred) and truth
    n = len(samples)
    return {"đồng ý với người": round(agree / n, 3),
            "judge quá nới (FP)": fp, "judge quá chặt (FN)": fn,
            "kết luận": "dùng được" if agree / n >= 0.85 else "PHẢI SỬA PROMPT JUDGE"}


# ---------- chỉ số phân loại ----------
def classification_metrics(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs: [(dự đoán, thực tế)]"""
    tp = sum(1 for p, t in pairs if p and t)
    fp = sum(1 for p, t in pairs if p and not t)
    fn = sum(1 for p, t in pairs if not p and t)
    tn = sum(1 for p, t in pairs if not p and not t)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": round(prec, 3), "recall": round(rec, 3),
            "f1": round(f1, 3),
            "accuracy": round((tp + tn) / max(len(pairs), 1), 3)}
```

`exercises/day67/run_eval.py`:

```python
from leanai_core.llm import LLMClient
from leanai_core.eval_dataset import EvalSet
from leanai_core.scorers import (score_enum, score_bool, score_number,
                                 classification_metrics, calibrate, judge_message)

llm = LLMClient()
ds = EvalSet.load("data/eval-50.json")
dev, test = ds.split(0.4)

def predict(case):
    """Thay bằng pipeline thật của bạn."""
    from projects.capstone.opportunity import detect          # Ngày 82
    return detect(case.input["customer"], case.input["today"])

pairs, details = [], []
for c in dev.cases:
    pred = predict(c)
    exp = c.expected
    scores = [
        score_bool(pred.get("has_opportunity"), exp["has_opportunity"], "có cơ hội"),
        score_enum(pred.get("opportunity_type"), exp.get("opportunity_type"), "loại"),
        score_bool(pred.get("should_contact"), exp.get("should_contact"), "nên liên hệ"),
        score_number(pred.get("estimated_value_vnd"), exp.get("estimated_value_vnd"),
                     tol=0.02, name="giá trị"),
    ]
    pairs.append((bool(pred.get("has_opportunity")), bool(exp["has_opportunity"])))
    failed = [s for s in scores if not s.passed]
    if failed:
        details.append((c.id, c.group, [f"{s.name}: {s.detail}" for s in failed]))

print("=== CHỈ SỐ PHÂN LOẠI (dev set) ===")
for k, v in classification_metrics(pairs).items():
    print(f"  {k}: {v}")

print(f"\n=== {len(details)} CA THẤT BẠI ===")
for cid, group, errs in details[:10]:
    print(f"  [{cid}] ({group}) {'; '.join(errs)[:110]}")

print("\n=== HIỆU CHUẨN LLM-JUDGE ===")
# Bạn tự chuẩn bị 20 mẫu có nhãn người
samples = []          # [{"customer":..., "message":..., "human_verdict": True}]
if samples:
    for k, v in calibrate(llm, samples).items():
        print(f"  {k}: {v}")
else:
    print("  (chưa có mẫu hiệu chuẩn — làm Bài 2)")
print("\n" + llm.usage.report())
```

---

## 4. Bài tập

**Bài 1 — Chạy eval.** Chạy trên dev set. Ghi precision/recall/F1. Phân tích: FP nhiều hơn hay FN nhiều hơn? Điều đó nói gì về ngưỡng của bạn?

**Bài 2 — Hiệu chuẩn judge.** Chuẩn bị 20 tin nhắn (10 tốt, 10 có lỗi cố ý), tự gán nhãn. Chạy `calibrate()`. Nếu đồng ý < 85% → sửa prompt judge, lặp lại đến khi đạt.

**Bài 3 — Thiên lệch độ dài.** Tạo 2 phiên bản cùng nội dung: 30 từ và 90 từ. Judge có ưu ái bản dài không? Nếu có → sửa prompt và đo lại.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 67 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Chấm deterministic cho mọi thứ có thể chấm bằng code
- [ ] LLM-judge đồng ý với người ≥ 85% (có số liệu hiệu chuẩn)
- [ ] Có precision/recall/F1 trên dev set
- [ ] Kiểm tra được thiên lệch độ dài của judge
- [ ] Quiz ≥ 80%
