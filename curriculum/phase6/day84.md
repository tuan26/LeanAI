# NGÀY 84 — Explanation layer

> Phase 6 · 15' thiết kế — 105' code
> Đây là chỗ **LLM xuất hiện lần đầu** trong luồng nghiệp vụ.

## 🎯 Mục tiêu

Giải thích "vì sao khách này" cho nhân viên đọc trong 10 giây — mọi câu đều dẫn số liệu thật.

---

## 1. Thiết kế (15 phút)

### 1.1 Phân chia trách nhiệm

```
CODE quyết định : ai là cơ hội, giá trị bao nhiêu, xác suất bao nhiêu   (Ngày 82-83)
LLM chỉ làm     : diễn đạt những con số đó thành câu người đọc dễ hiểu
```

LLM **không được** thêm thông tin, không được suy luận thêm, không được tính toán.

### 1.2 Định dạng đầu ra

```
💰 4.800.000đ  ·  khả năng 62%  ·  ưu tiên 2

• Còn 4/10 buổi trị liệu da mặt, hết hạn sau 25 ngày
• Đã 112 ngày chưa quay lại — quá lâu so với chu kỳ thường của chị
• Khách thân thiết: đã chi 38 triệu trong 2 năm

⚠ Từng phàn nàn chờ lâu (03/2026) — nên đề xuất khung giờ vắng
👉 Gợi ý: nhắn Zalo (khách không thích gọi điện), nhấn mạnh hạn dùng
```

Ba gạch đầu dòng, mỗi gạch **một con số**. Không văn vẻ.

### 1.3 Chống bịa ở tầng này

```
1. Chỉ đưa reason_data vào prompt, không đưa gì khác
2. Guardrail: mọi số trong output phải có trong reason_data
3. Nếu vi phạm → hiển thị bản template không có LLM
```

Luôn có đường lui không cần AI (Ngày 74).

---

## 2. Code (105 phút)

`backend/app/services/explainer.py`:

```python
"""Giải thích cơ hội — LLM diễn đạt, CODE cung cấp số liệu."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from leanai_core.llm import LLMClient

llm = LLMClient()

SYSTEM = """VAI TRÒ: bạn viết phần giải thích ngắn cho nhân viên chăm sóc khách hàng của
spa/phòng khám tại Việt Nam. Người đọc đang bận, cần hiểu trong 10 giây để quyết định
có liên hệ khách này không.

QUY TẮC TUYỆT ĐỐI:
- CHỈ dùng số liệu trong <data>. KHÔNG thêm bất kỳ con số nào khác.
- KHÔNG tự tính toán. Mọi con số đã được tính sẵn trong <data>.
- KHÔNG suy đoán về cảm xúc, ý định hay hoàn cảnh của khách.
- Mỗi gạch đầu dòng phải chứa ÍT NHẤT một con số từ <data>.
- Nếu <data> có ghi_chu tiêu cực, thêm một dòng cảnh báo bắt đầu bằng "⚠".
- Thêm đúng một dòng gợi ý cách tiếp cận, bắt đầu bằng "👉".

CẤM: hứa hẹn ưu đãi; dùng từ "khuyến mãi", "giảm giá"; viết quá 3 gạch đầu dòng;
viết lời chào hay lời kết.

ĐỊNH DẠNG:
• <ý 1 có số>
• <ý 2 có số>
• <ý 3 có số>
⚠ <cảnh báo nếu có>
👉 <gợi ý cách tiếp cận>"""

TEMPLATE_FALLBACK = """• Còn {buoi_con_lai}/{tong_buoi} buổi {goi}, hết hạn {ngay_het_han}
• Đã {vang_mat_ngay} ngày chưa quay lại
• Giá trị chưa sử dụng: {gia_tri_chua_dung:,}đ
👉 Liên hệ nhắc khách sử dụng trước khi hết hạn"""


@dataclass
class Explanation:
    text: str
    generated_by: str            # "llm" | "template"
    cost: float = 0.0
    warnings: list[str] = None


def _numbers(t: str) -> set[str]:
    return {re.sub(r"[.,\s]", "", x) for x in re.findall(r"\d[\d.,\s]*\d|\d", t)}


def verify_no_ghost_numbers(text: str, data: dict) -> list[str]:
    src = json.dumps(data, ensure_ascii=False, default=str)
    ghost = {g for g in (_numbers(text) - _numbers(src)) if len(g) > 1}
    return sorted(ghost)


def explain(reason_data: dict, *, probability: float, expected_value: int,
            factors: list[str] | None = None) -> Explanation:
    payload = {**reason_data,
               "kha_nang_phan_hoi": f"{probability:.0%}",
               "gia_tri_ky_vong": expected_value}
    prompt = (f"<data>\n{json.dumps(payload, ensure_ascii=False, default=str, indent=1)}\n</data>\n\n"
              f"<yeu_to_anh_huong>\n" +
              "\n".join(f"- {f}" for f in (factors or [])) +
              "\n</yeu_to_anh_huong>\n\n"
              "Viết phần giải thích theo đúng định dạng.")

    r = llm.complete(prompt, system=SYSTEM, temperature=0.2,
                     max_tokens=350, tag="explain")

    ghost = verify_no_ghost_numbers(r.text, payload)
    if ghost:
        # fallback: không hiển thị nội dung không xác minh được
        return Explanation(
            TEMPLATE_FALLBACK.format(**reason_data), "template", r.cost,
            [f"LLM sinh số không có trong dữ liệu: {ghost} — đã dùng bản mẫu"])

    banned = [w for w in ("khuyến mãi", "giảm giá", "miễn phí", "tặng")
              if w in r.text.lower()]
    if banned:
        return Explanation(TEMPLATE_FALLBACK.format(**reason_data), "template", r.cost,
                           [f"LLM dùng từ cấm: {banned}"])

    return Explanation(r.text.strip(), "llm", r.cost, [])


def explain_batch(items: list[dict], max_workers: int = 5) -> list[Explanation]:
    """Chạy song song — job đêm xử lý ~80 cơ hội."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers) as ex:
        return list(ex.map(
            lambda i: explain(i["reason_data"], probability=i["probability"],
                              expected_value=i["expected_value_vnd"],
                              factors=i.get("factors")), items))
```

### Test

`backend/tests/test_explainer.py`:

```python
from app.services.explainer import explain, verify_no_ghost_numbers

DATA = {"ten": "Nguyễn Thị Lan", "goi": "Trị liệu da mặt", "tong_buoi": 10,
        "da_dung": 6, "buoi_con_lai": 4, "gia_tri_chua_dung": 4_800_000,
        "vang_mat_ngay": 112, "ngay_het_han": "2026-10-12", "con_lai_ngay": 25,
        "ghi_chu": "phàn nàn chờ lâu 03/2026", "lifetime_value": 38_000_000}


def test_khong_co_so_bia():
    e = explain(DATA, probability=0.62, expected_value=2_976_000)
    assert not verify_no_ghost_numbers(e.text, DATA)


def test_co_canh_bao_khi_tung_phan_nan():
    e = explain(DATA, probability=0.62, expected_value=2_976_000)
    assert "⚠" in e.text


def test_khong_dung_tu_cam():
    e = explain(DATA, probability=0.62, expected_value=2_976_000)
    assert not any(w in e.text.lower() for w in ("khuyến mãi", "giảm giá"))


def test_fallback_khi_llm_bia():
    fake = "• Khách còn 7 buổi và được giảm 30%"
    assert verify_no_ghost_numbers(fake, DATA)


def test_do_dai_hop_ly():
    e = explain(DATA, probability=0.62, expected_value=2_976_000)
    assert len([l for l in e.text.splitlines() if l.strip().startswith("•")]) <= 3
```

---

## 3. Việc phải làm

1. Chạy explain cho **30 cơ hội** từ Ngày 83.
2. Đọc tay tất cả. Đếm: bao nhiêu cái bị fallback về template? Vì sao?
3. Đo: chi phí trung bình/giải thích, thời gian, tỉ lệ dùng LLM thành công.
4. Tự chấm: bạn có quyết định được "liên hệ hay không" trong 10 giây khi đọc không?

---

## 4. PASS/FAIL

- [ ] Mọi giải thích **không có số bịa** (verify bằng code)
- [ ] Tỉ lệ fallback < 10%
- [ ] Có cảnh báo ⚠ khi khách có ghi chú tiêu cực
- [ ] Có gợi ý 👉 phù hợp với kênh khách ưa thích
- [ ] Chi phí < 0.002 USD/giải thích
- [ ] Chạy batch 30 cơ hội < 30 giây (song song)
- [ ] 5 test pass

---

## 5. Quiz + commit

```powershell
python quiz\quiz.py --day 84 ; python quiz\quiz.py --review
git add . ; git commit -m "day 84: explanation layer with anti-hallucination"
```
