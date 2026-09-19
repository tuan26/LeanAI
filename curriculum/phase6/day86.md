# NGÀY 86 — Agent: draft message

> Phase 6 · 15' thiết kế — 105' code + đánh giá

## 🎯 Mục tiêu

Tin nhắn Zalo/SMS **nghe như người thật viết**, số liệu chính xác tuyệt đối, qua được guardrail.

---

## 1. Thiết kế (15 phút)

### 1.1 Số liệu do CODE chèn, văn do LLM viết

```
❌ LLM viết cả câu có số     → nguy cơ bịa
✅ LLM viết khung, code thay  → số luôn đúng

LLM sinh: "Chị {ten} ơi, gói {goi} của chị còn {buoi_con_lai} buổi
           và hết hạn sau {con_lai_ngay} ngày ạ..."
CODE thay: → "Chị Lan ơi, gói Trị liệu da mặt của chị còn 4 buổi
              và hết hạn sau 25 ngày ạ..."
```

Đây là kỹ thuật quan trọng nhất hôm nay. Nó biến hallucination số liệu từ "hiếm khi" thành "không thể".

### 1.2 Diệt "mùi AI"

| Dấu hiệu AI | Cách chữa |
|---|---|
| "Hy vọng tin nhắn này tìm thấy bạn khoẻ mạnh" | few-shot bằng tin người thật viết |
| Quá trang trọng | quy tắc xưng hô cụ thể |
| Cấu trúc lặp lại y hệt | temperature 0.7 + đa dạng mẫu mở đầu |
| Dài dòng | giới hạn cứng 2–3 câu |
| Emoji tràn lan | tối đa 1 |

### 1.3 Mỗi loại cơ hội một giọng khác

```
EXPIRING_SOON   : nhấn deadline, giọng nhắc nhở thân thiện
OVERDUE_REVISIT : hỏi thăm trước, nhắc gói sau
UNUSED_PACKAGE  : nhấn giá trị chưa dùng, gợi ý đặt lịch
```

---

## 2. Code (105 phút)

`backend/app/services/drafter.py`:

```python
"""Soạn nháp tin nhắn — LLM viết khung, CODE chèn số."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from leanai_core.llm import LLMClient
from leanai_core.validate import Constraints

from ..models import OppType

llm = LLMClient()

SYSTEM = """VAI TRÒ: bạn là nhân viên chăm sóc khách hàng của spa cao cấp tại Việt Nam,
đang soạn tin nhắn Zalo gửi khách hàng thân thiết.

QUY TẮC VIẾT:
- Xưng "em", gọi khách bằng "chị"/"anh" + tên (dùng biến {ten})
- ĐÚNG 2-3 câu ngắn. Tổng dưới 55 từ.
- Nêu ĐÚNG MỘT lý do cụ thể để khách quay lại
- Kết bằng một câu hỏi mở về thời gian
- Tối đa 1 emoji, hoặc không có
- Giọng tự nhiên như người Việt nhắn tin, KHÔNG trang trọng kiểu thư từ

BẮT BUỘC dùng BIẾN thay cho số liệu, viết đúng dạng {ten_bien}:
{ten} {goi} {buoi_con_lai} {tong_buoi} {con_lai_ngay} {vang_mat_ngay} {ngay_het_han}
TUYỆT ĐỐI KHÔNG tự viết con số nào.

CẤM: từ "khuyến mãi", "ưu đãi", "giảm giá", "miễn phí", "tặng";
hứa hẹn bất cứ điều gì; lời chào dài dòng; câu kết kiểu "mong sớm gặp lại".

CHỈ trả về nội dung tin nhắn, không giải thích."""

FEWSHOT = """Ví dụ tin nhắn đạt chuẩn (do nhân viên thật viết):

[gói sắp hết hạn]
Chị {ten} ơi, gói {goi} của chị còn {buoi_con_lai} buổi mà chỉ còn {con_lai_ngay} ngày
nữa là hết hạn ạ. Em giữ giúp chị một khung giờ vắng nhé, chị sắp xếp được hôm nào ạ?

[lâu không quay lại]
Chị {ten} ơi, lâu quá không thấy chị ghé ạ. Gói {goi} của chị vẫn còn {buoi_con_lai}
buổi chưa dùng. Tuần này chị rảnh buổi nào để em xếp lịch cho chị ạ?

[mua gói chưa dùng]
Anh {ten} ơi, em thấy gói {goi} anh mua vẫn còn nguyên {buoi_con_lai} buổi ạ.
Anh muốn bắt đầu từ tuần này không, em xếp khung giờ ít khách cho anh nhé?

[khách từng phàn nàn chờ lâu]
Chị {ten} ơi, gói của chị còn {buoi_con_lai} buổi ạ. Lần này em xếp chị vào khung
giờ vắng để không phải chờ như lần trước. Chị đi buổi sáng hôm nào được ạ?"""

TONE_BY_TYPE = {
    OppType.EXPIRING_SOON: "Nhấn mạnh hạn sử dụng sắp hết, giọng nhắc nhở nhẹ nhàng.",
    OppType.OVERDUE_REVISIT: "Hỏi thăm trước, nhắc gói sau. Không trách móc.",
    OppType.UNUSED_PACKAGE: "Nhấn mạnh gói còn nguyên giá trị, gợi ý bắt đầu.",
}

PLACEHOLDER = re.compile(r"\{(\w+)\}")


@dataclass
class Draft:
    text: str                  # đã thay biến
    template: str              # bản còn biến, để audit
    cost: float = 0.0
    violations: list[str] = field(default_factory=list)


def render(template: str, data: dict) -> tuple[str, list[str]]:
    """Thay biến bằng số liệu thật. Biến không có dữ liệu -> lỗi."""
    missing = []

    def sub(m):
        key = m.group(1)
        if key not in data or data[key] in (None, ""):
            missing.append(key)
            return m.group(0)
        v = data[key]
        return f"{v:,}".replace(",", ".") if isinstance(v, int) and v >= 1000 else str(v)

    return PLACEHOLDER.sub(sub, template), missing


def draft_message(reason_data: dict, *, opp_type: OppType, channel: str = "zalo",
                  explanation: str = "", max_retries: int = 2) -> Draft:
    ctx = {k: reason_data.get(k) for k in
           ("goi", "buoi_con_lai", "tong_buoi", "con_lai_ngay", "vang_mat_ngay",
            "ngay_het_han")}
    note = reason_data.get("ghi_chu", "")

    prompt = (f"{FEWSHOT}\n\n"
              f"Bây giờ viết cho trường hợp sau.\n"
              f"Loại cơ hội: {opp_type.value}. {TONE_BY_TYPE.get(opp_type, '')}\n"
              f"Ghi chú về khách (nếu có): {note or 'không có'}\n"
              f"Kênh gửi: {channel}\n\n"
              f"Nhớ: dùng BIẾN {{ten}} {{goi}} {{buoi_con_lai}}..., không viết số.")

    rules = (Constraints().max_words(55)
             .forbidden(["khuyến mãi", "ưu đãi", "giảm giá", "miễn phí", "tặng"])
             .max_emoji(1).must_match(r"\?", "phải có câu hỏi"))

    messages = [{"role": "user", "content": prompt}]
    total_cost = 0.0
    for attempt in range(max_retries + 1):
        r = llm.chat(messages, system=SYSTEM, temperature=0.7,
                     max_tokens=250, tag="draft")
        total_cost += r.cost
        template = r.text.strip()

        errs = [v.detail for v in rules.run(template)]
        # LLM không được viết số trực tiếp (trừ số trong biến)
        raw_numbers = re.findall(r"(?<!\{)\b\d[\d.,]*\b(?![^{]*\})", template)
        if raw_numbers:
            errs.append(f"viết số trực tiếp thay vì dùng biến: {raw_numbers[:3]}")

        if not errs:
            text, missing = render(template, {**ctx, "ten": reason_data.get("ten", "")})
            if missing:
                errs.append(f"dùng biến không có dữ liệu: {missing}")
            else:
                return Draft(text, template, total_cost, [])

        if attempt < max_retries:
            messages += [{"role": "assistant", "content": template},
                         {"role": "user",
                          "content": f"Tin nhắn vi phạm: {'; '.join(errs)}. "
                                     f"Viết lại đúng quy tắc, CHỈ trả về tin nhắn."}]

    # thất bại -> template an toàn
    safe = ("Chị {ten} ơi, gói {goi} của chị còn {buoi_con_lai} buổi chưa dùng ạ. "
            "Chị sắp xếp được hôm nào để em xếp lịch cho chị ạ?")
    text, _ = render(safe, {**ctx, "ten": reason_data.get("ten", "")})
    return Draft(text, safe, total_cost, errs)
```

---

## 3. Đánh giá bắt buộc

### Bài test mù (30 phút)

1. Soạn **20 tin nhắn** bằng hệ thống.
2. Viết tay **5 tin nhắn** của chính bạn.
3. Trộn lẫn, gửi cho **3 người** (đồng nghiệp/bạn bè). Hỏi: *"Cái nào do máy viết?"*
4. Ghi tỉ lệ đoán đúng.

> Nếu người ta nhận ra > 70% tin do AI viết → few-shot của bạn chưa đủ tốt. Thu thập tin nhắn người thật viết và đưa vào.

### Đo tự động

```
Tỉ lệ qua guardrail lần 1  : ___%    (mục tiêu ≥ 85%)
Tỉ lệ phải dùng template   : ___%    (mục tiêu ≤ 5%)
Số liệu sai                : 0       (bắt buộc)
Độ dài trung bình          : ___ từ  (mục tiêu 35-50)
Chi phí/tin                : $___
```

---

## 4. PASS/FAIL

- [ ] LLM sinh **biến**, không sinh số trực tiếp
- [ ] `render()` thay số từ database, sai biến → phát hiện được
- [ ] 0 tin nhắn có số liệu sai trên 50 mẫu
- [ ] ≥ 85% qua guardrail ngay lần đầu
- [ ] Người thật đoán đúng "do AI viết" ≤ 70%
- [ ] Mỗi loại cơ hội có giọng khác nhau rõ rệt
- [ ] Có bản template an toàn khi LLM thất bại

---

## 5. Quiz + commit

```powershell
python quiz\quiz.py --day 86 ; python quiz\quiz.py --review
git add . ; git commit -m "day 86: message drafter with variable substitution"
```
