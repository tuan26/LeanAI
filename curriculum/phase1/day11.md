# NGÀY 11 — Instruction tuning

> Phase 1 · 25' lý thuyết — 15' tài liệu — 65' code — 15' note

## 🎯 Mục tiêu

Hiểu vì sao model "nghe lời", và biết khi nào **fine-tuning là câu trả lời** — khi nào chỉ là cách tiêu tiền vô ích.

---

## 1. Lý thuyết cốt lõi (25 phút)

### 1.1 Từ "tiếp tục văn bản" sang "làm theo yêu cầu"

Sau pretraining, model được huấn luyện tiếp trên tập cặp **(chỉ dẫn → phản hồi mẫu)** do người viết:

```json
{"instruction": "Tóm tắt đoạn sau thành 3 gạch đầu dòng", "input": "...", "output": "- ...\n- ...\n- ..."}
{"instruction": "Dịch sang tiếng Anh", "input": "Chào chị", "output": "Hello ma'am"}
```

Quy mô: hàng chục nghìn đến vài triệu ví dụ — nhỏ hơn pretraining hàng nghìn lần. Đây là bước **rẻ nhưng thay đổi hành vi nhiều nhất**.

### 1.2 Chat template — thứ bạn phải biết

Instruction tuning dạy model hiểu cấu trúc vai:

```
<|system|>Bạn là trợ lý chăm sóc khách hàng.<|end|>
<|user|>Khách này nên gọi lại không?<|end|>
<|assistant|>
```

Khi bạn gửi `messages=[{"role":"system",...},{"role":"user",...}]`, SDK dựng đúng chuỗi này. Hiểu điều đó giúp bạn:
- biết vì sao **system prompt có sức nặng hơn** user message,
- hiểu vì sao cần chặn người dùng chèn chuỗi giả vai (Ngày 28).

### 1.3 Ba cấp độ can thiệp hành vi model

| Cấp | Cách | Chi phí | Thời gian | Dùng khi |
|---|---|---|---|---|
| 1 | **Prompt engineering** | ~0 | phút | 90% trường hợp — luôn thử trước |
| 2 | **Few-shot trong prompt** | token mỗi lượt | phút | cần định dạng/phong cách cụ thể |
| 3 | **Fine-tuning** | cao | ngày–tuần | 3 điều kiện dưới |

**Chỉ fine-tune khi đủ CẢ BA:**
1. Đã thử hết prompt + few-shot mà vẫn không đạt,
2. Có ≥ 500–1000 ví dụ chất lượng cao, nhất quán,
3. Tác vụ lặp lại đủ nhiều để tiết kiệm token bù được chi phí train.

> Fine-tuning dạy model **cách làm** (phong cách, định dạng, giọng văn). Nó **không** dạy model **kiến thức mới** một cách đáng tin. Muốn thêm kiến thức → RAG. Nhầm lẫn này là sai lầm tốn kém nhất mà tôi thấy ở các đội mới làm AI.

### 1.4 LoRA — fine-tuning giá rẻ

Thay vì cập nhật toàn bộ tham số, chỉ train thêm vài ma trận nhỏ chèn cạnh model gốc. Giảm chi phí hàng chục lần, có thể tháo lắp như plugin. Nếu sau 90 ngày bạn cần fine-tune, đây là hướng đi.

### 1.5 Ứng dụng: CareDesk-AI có cần fine-tune không?

Câu trả lời cho 90 ngày này: **không**.

| Nhu cầu | Giải pháp đúng |
|---|---|
| Tin nhắn đúng giọng thương hiệu | few-shot 5 ví dụ trong prompt |
| Biết bảng giá phòng khám | RAG |
| Output JSON ổn định | schema + validation (Ngày 30) |
| Xưng hô đúng vai vế tiếng Việt | system prompt + few-shot |

Quay lại cân nhắc fine-tune khi bạn đã có **10.000 tin nhắn được nhân viên duyệt** — lúc đó dữ liệu mới đủ tốt.

---

## 2. Tài liệu (15 phút)

| Nguồn | Link | Bắt buộc |
|---|---|---|
| Anthropic — System prompts | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/system-prompts | ✅ |
| InstructGPT paper (abstract + Fig.1) | https://arxiv.org/abs/2203.02155 | ✅ |
| LoRA paper (abstract) | https://arxiv.org/abs/2106.09685 | tuỳ chọn |

---

## 3. Thực hành (65 phút)

`exercises/day11/steering.py` — leo thang 3 cấp can thiệp trên cùng một bài toán:

```python
"""Ngày 11: cùng 1 tác vụ, 3 cấp can thiệp. Đo xem cấp nào đủ."""
import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

CASE = ("Khách: chị Nguyễn Thị Lan, 42 tuổi. Gói: Trị liệu da mặt 10 buổi, còn 4 buổi, "
        "hết hạn sau 25 ngày. Lần cuối đến: 112 ngày trước. Từng phàn nàn: chờ lâu.")


def run(system: str, user: str, temperature: float = 0.7) -> str:
    r = client.messages.create(
        model=MODEL, max_tokens=300, temperature=temperature,
        system=system, messages=[{"role": "user", "content": user}],
    )
    return r.content[0].text.strip()


# --- Cấp 0: không hướng dẫn gì ---
L0_SYS = ""
L0_USER = f"{CASE}\n\nViết tin nhắn mời khách quay lại."

# --- Cấp 1: prompt engineering ---
L1_SYS = """Bạn là nhân viên chăm sóc khách hàng của spa cao cấp tại Việt Nam.
Quy tắc viết tin nhắn Zalo:
- Xưng "em", gọi khách theo "chị/anh + tên"
- Tối đa 55 từ
- Nêu đúng 1 lý do cụ thể để khách quay lại (dựa trên dữ liệu được cung cấp)
- Không dùng từ "khuyến mãi", "ưu đãi sốc", không dùng emoji quá 1 cái
- Kết bằng 1 câu hỏi mở về thời gian
- Nếu khách từng phàn nàn, ghi nhận nhẹ nhàng, không xin lỗi lê thê"""
L1_USER = L0_USER

# --- Cấp 2: few-shot ---
L2_SYS = L1_SYS
L2_USER = f"""Ví dụ tin nhắn đạt chuẩn:

[Khách: chị Mai, gói massage còn 2 buổi, hết hạn 10 ngày nữa, lần cuối 80 ngày trước]
Chị Mai ơi, em thấy gói massage của chị còn 2 buổi và sắp hết hạn trong 10 ngày nữa ạ.
Em giữ giúp chị một khung giờ vắng để chị không phải chờ nhé. Chị sắp xếp được buổi
chiều thứ mấy tuần này ạ?

[Khách: anh Hùng, gói chăm sóc da còn 5 buổi, lần cuối 150 ngày trước, từng phàn nàn giá]
Anh Hùng ơi, gói chăm sóc da của anh vẫn còn 5 buổi chưa dùng ạ. Em đã ghi chú để lần
này anh được xếp vào khung giờ ít khách, làm nhanh gọn hơn. Anh ghé lại tuần này được
không ạ?

Giờ viết cho trường hợp sau, đúng phong cách trên:
{CASE}"""

if __name__ == "__main__":
    for name, sys_p, user_p in (
        ("CẤP 0 — không hướng dẫn", L0_SYS, L0_USER),
        ("CẤP 1 — prompt engineering", L1_SYS, L1_USER),
        ("CẤP 2 — few-shot", L2_SYS, L2_USER),
    ):
        out = run(sys_p, user_p)
        print(f"\n{'='*66}\n{name}  ({len(out.split())} từ)\n{'='*66}\n{out}")
```

### Chấm điểm bắt buộc

Tự chấm mỗi cấp theo 6 tiêu chí (✅/❌): xưng hô đúng · ≤55 từ · lý do cụ thể · không dùng từ cấm · kết bằng câu hỏi · xử lý khéo lời phàn nàn.

| Cấp | Điểm /6 |
|---|---|
| Cấp 0 | |
| Cấp 1 | |
| Cấp 2 | |

**Kết luận bạn phải rút ra:** nếu cấp 1 hoặc 2 đã đạt 6/6 → **fine-tuning là lãng phí tiền**.

---

## 4. Bài tập

**Bài 1 — Chạy 5 khách khác nhau** qua cả 3 cấp (15 output). Lập bảng điểm. Tính điểm trung bình từng cấp. Cấp nào đủ tốt để đưa vào sản phẩm?

**Bài 2 — Thư viện system prompt.** Tạo `templates/system-prompts.md` với 3 prompt hoàn chỉnh, mỗi cái có: vai trò, quy tắc, ràng buộc định dạng, điều cấm.
- `customer_message_writer` (soạn tin nhắn)
- `opportunity_explainer` (giải thích vì sao khách này là cơ hội)
- `document_qa` (trả lời từ tài liệu, phải trích nguồn)

Bạn sẽ dùng lại chúng từ Ngày 24 đến Ngày 90.

**Bài 3 — Quyết định.** Viết 300 từ trong `progress/notes/day11.md`: *"CareDesk-AI có nên fine-tune không? Nếu có thì lúc nào, cần gì, tốn gì?"* Dùng đúng 3 điều kiện ở mục 1.3.

---

## 5. Quiz nhớ bài

```powershell
python quiz\quiz.py --day 11
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Giải thích được instruction tuning và chat template
- [ ] Thuộc 3 điều kiện được phép fine-tune
- [ ] Phân biệt rõ: fine-tune dạy *cách làm*, RAG cung cấp *kiến thức*
- [ ] Có bảng điểm 3 cấp trên ≥ 5 trường hợp
- [ ] `templates/system-prompts.md` có đủ 3 prompt
- [ ] Quiz ≥ 80%
