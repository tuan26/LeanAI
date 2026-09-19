# NGÀY 27 — Self-verification (critic pass)

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Thêm lớp **tự kiểm tra** vào pipeline — và đo xem nó có thật sự đáng tiền không.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Mẫu Generator–Critic

```
Prompt ──► GENERATOR ──► bản nháp ──► CRITIC ──► phán quyết
                            ▲                      │
                            └──── sửa lại ◄────────┘  (tối đa N vòng)
```

Critic hiệu quả **hơn hẳn** khi:
- có tiêu chí kiểm tra rõ ràng, liệt kê được,
- được xem **nguồn dữ liệu gốc** để đối chiếu,
- được yêu cầu **tìm lỗi**, không phải "đánh giá chất lượng".

### 1.2 Vì sao "hãy kiểm tra lại" thường vô dụng

Hỏi model *"câu trả lời trên có đúng không?"* → nó sẽ nói "đúng" (sycophancy, Ngày 12).

Thay bằng:
```
Liệt kê MỌI lỗi trong output dưới đây theo từng tiêu chí. 
Nếu một tiêu chí không có lỗi, ghi "OK". 
Bạn BẮT BUỘC phải tìm ít nhất 1 điểm có thể cải thiện.
```

### 1.3 Ba loại kiểm tra — dùng đúng công cụ

| Loại | Dùng gì | Ví dụ |
|---|---|---|
| **Xác định được bằng luật** | **CODE** | độ dài, từ cấm, JSON hợp lệ, số có trong nguồn |
| **Cần đối chiếu nguồn** | LLM critic | mọi khẳng định có được tài liệu hỗ trợ không |
| **Cần cảm nhận** | **NGƯỜI** | giọng văn có tự nhiên không, khách có khó chịu không |

> Đừng dùng LLM để kiểm tra thứ code kiểm tra được. Chậm hơn, đắt hơn, kém tin cậy hơn.

### 1.4 Chi phí thật của critic

Mỗi vòng critic ≈ +60–100% chi phí và latency. Chỉ dùng khi:
- hậu quả của lỗi lớn (gửi tin sai cho khách, báo cáo cho sếp),
- hoặc đo được rằng nó bắt được lỗi thật với tỉ lệ đáng kể.

Đo trước, dùng sau.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Increase output consistency | https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency |
| Self-Refine (paper, abstract) | https://arxiv.org/abs/2303.17651 |

---

## 3. Thực hành (80 phút)

`leanai_core/critic.py`:

```python
"""Generator - Critic - Refine."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .jsonutil import safe_json_loads


@dataclass
class Critique:
    passed: bool
    issues: list[dict]          # [{"criterion":..., "severity":..., "detail":...}]
    raw: str

    def blocking(self) -> list[dict]:
        return [i for i in self.issues if i.get("severity") in ("cao", "high")]


CRITIC_SYSTEM = """Bạn là người kiểm định chất lượng khắt khe. Nhiệm vụ của bạn là TÌM LỖI,
không phải khen. Bạn BẮT BUỘC kiểm tra từng tiêu chí và báo cáo trung thực.
Không được bỏ qua lỗi vì lịch sự. Không được bịa lỗi không có thật."""


def critique(llm, *, source: str, output: str, criteria: list[str]) -> Critique:
    crit_list = "\n".join(f"{i+1}. {c}" for i, c in enumerate(criteria))
    prompt = f"""<source_data>
{source}
</source_data>

<output_to_check>
{output}
</output_to_check>

TIÊU CHÍ KIỂM TRA:
{crit_list}

Với TỪNG tiêu chí, xác định có lỗi hay không. Trả về CHỈ JSON:
{{"issues": [{{"criterion": "<số thứ tự + tên>", "severity": "cao|trung_binh|thap",
"detail": "<mô tả lỗi cụ thể, trích dẫn đoạn sai>"}}], "verdict": "PASS|FAIL"}}

Nếu không có lỗi nào, trả về {{"issues": [], "verdict": "PASS"}}."""

    r = llm.complete(prompt, system=CRITIC_SYSTEM, temperature=0,
                     max_tokens=800, tag="critic")
    d = safe_json_loads(r.text, {"issues": [], "verdict": "PASS"})
    return Critique(passed=d.get("verdict") == "PASS" and not d.get("issues"),
                    issues=d.get("issues", []), raw=r.text)


def generate_refine(llm, *, gen_prompt: str, source: str, criteria: list[str],
                    system: str = "", max_rounds: int = 2, **kw):
    """Sinh -> phê bình -> sửa. Trả về (output, số vòng, lịch sử)."""
    history = []
    r = llm.complete(gen_prompt, system=system, tag="generator", **kw)
    out = r.text
    for rnd in range(max_rounds):
        c = critique(llm, source=source, output=out, criteria=criteria)
        history.append({"round": rnd, "output": out, "issues": c.issues})
        if c.passed:
            return out, rnd, history
        issues = "\n".join(f"- [{i['severity']}] {i['criterion']}: {i['detail']}"
                           for i in c.issues)
        print(f"  [vòng {rnd+1}] {len(c.issues)} lỗi:\n{issues}")
        r = llm.complete(
            f"{gen_prompt}\n\nBản nháp trước:\n{out}\n\n"
            f"Người kiểm định phát hiện các lỗi sau:\n{issues}\n\n"
            f"Viết lại bản mới sửa hết các lỗi trên. CHỈ trả về bản mới.",
            system=system, tag="refine", **kw)
        out = r.text
    return out, max_rounds, history


# ---- kiểm tra bằng CODE, luôn chạy trước critic LLM ----
def numbers_in_source(source: str, output: str) -> list[str]:
    """Trả về các con số xuất hiện trong output nhưng KHÔNG có trong nguồn."""
    def nums(t):
        return {re.sub(r"[.,]", "", n) for n in re.findall(r"\d[\d.,]*", t)}
    return sorted(nums(output) - nums(source))
```

`exercises/day27/critic_test.py`:

```python
from leanai_core.llm import LLMClient
from leanai_core.critic import generate_refine, numbers_in_source

llm = LLMClient()

SOURCE = """Khách: Nguyễn Thị Lan. Gói Trị liệu da mặt 10 buổi, đã dùng 6, còn 4 buổi.
Giá gói 12.000.000đ. Hết hạn 12/10/2026 (còn 25 ngày). Vắng mặt 112 ngày.
Ghi chú: từng phàn nàn chờ lâu (03/2026), thích khung giờ sáng, không thích bị gọi điện."""

CRITERIA = [
 "Mọi con số trong output phải xuất hiện trong <source_data>",
 "Không được hứa hẹn điều gì không có trong dữ liệu (giảm giá, tặng buổi, ưu đãi)",
 "Phải xưng 'em' và gọi khách 'chị + tên'",
 "Độ dài 2-3 câu, tối đa 55 từ",
 "Không dùng các từ: khuyến mãi, ưu đãi, sốc, giảm giá",
 "Phải kết thúc bằng một câu hỏi về thời gian",
 "Phải tôn trọng ghi chú CRM (khách không thích bị gọi điện, thích buổi sáng)",
]

out, rounds, hist = generate_refine(
    llm,
    gen_prompt=f"<data>{SOURCE}</data>\n\nViết tin nhắn Zalo mời khách quay lại.",
    source=SOURCE, criteria=CRITERIA,
    system="Bạn là nhân viên CSKH spa Việt Nam.",
    temperature=0.7, max_tokens=250, max_rounds=2)

print(f"\n=== KẾT QUẢ sau {rounds} vòng sửa ===\n{out}")
print(f"\nSố từ: {len(out.split())}")
bad = numbers_in_source(SOURCE, out)
print(f"Số không có trong nguồn: {bad or 'không có ✓'}")
print("\n" + llm.usage.report())
```

---

## 4. Bài tập

**Bài 1 — Critic có bắt được lỗi thật không?** Tự tay viết 10 output **cố tình sai** (sai số liệu, hứa giảm giá, quá dài, gọi điện dù khách không thích). Chạy critic. Đo: bắt được bao nhiêu / 10? Bỏ sót loại lỗi nào?

**Bài 2 — Critic có báo lỗi giả không?** Viết 10 output **hoàn toàn đúng**. Chạy critic. Đếm số lỗi giả (false positive). Nếu critic luôn tìm ra lỗi kể cả khi không có → prompt "bắt buộc tìm 1 điểm cải thiện" đang phản tác dụng. Sửa lại.

**Bài 3 — Bảng quyết định.** Lập bảng: với mỗi tiêu chí trong `CRITERIA`, ghi nên kiểm tra bằng **CODE / LLM / NGƯỜI** và lý do. Chuyển hết những cái CODE làm được sang `Constraints` (Ngày 25), đo lại chi phí critic giảm bao nhiêu.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 27 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `generate_refine` chạy, in rõ lỗi từng vòng
- [ ] Có số liệu: bắt được bao nhiêu lỗi thật / 10
- [ ] Có số liệu: bao nhiêu lỗi giả / 10
- [ ] Đã chuyển các kiểm tra luật-định sang code, còn LLM chỉ làm phần đối chiếu nguồn
- [ ] Trả lời được: critic có đáng tiền cho tác vụ này không
- [ ] Quiz ≥ 80%
