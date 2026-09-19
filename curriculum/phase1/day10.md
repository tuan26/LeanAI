# NGÀY 10 — Pretraining

> Phase 1 · 30' lý thuyết — 20' tài liệu — 55' phân tích — 15' note
> Ngày nhẹ về code, nặng về **nhận định**. Đây là ngày giúp bạn trả lời được câu khách hàng hay hỏi: *"AI có biết về công ty tôi không?"*

## 🎯 Mục tiêu

Hiểu vòng đời một model: pretraining → instruction tuning (Ngày 11) → RLHF (Ngày 12), và biết **kiến thức của model đến từ đâu, dừng ở đâu**.

---

## 1. Lý thuyết cốt lõi (30 phút)

### 1.1 Pretraining làm gì

Một nhiệm vụ duy nhất, lặp hàng nghìn tỷ lần:

```
Cho: "Phòng khám mở cửa từ 9 giờ"
Che: "Phòng khám mở cửa từ [?]"
Model đoán → so với "9" → tính loss → cập nhật tham số
```

Không nhãn, không người chú thích. Dữ liệu tự sinh nhãn cho chính nó (**self-supervised**). Đây là lý do có thể train trên toàn bộ internet.

### 1.2 Quy mô

| Thành phần | Bậc độ lớn |
|---|---|
| Dữ liệu | nghìn tỷ token (web, sách, code, wiki, diễn đàn) |
| Tính toán | hàng nghìn GPU × hàng tháng |
| Chi phí | hàng triệu đến hàng trăm triệu USD |
| Kết quả | một model **base** — biết rất nhiều, nhưng không biết nghe lời |

Đây là lý do mục "5 thứ không học" trong README có *training LLM từ đầu*. Bạn không có vài triệu USD, và bạn cũng không cần.

### 1.3 Model base khác model chat thế nào

```
Base model, prompt: "Cách chăm sóc da sau peel là"
→ "gì? Đây là câu hỏi nhiều người quan tâm. Cách chăm sóc da sau peel là..."
   (nó CHỈ tiếp tục văn bản, không trả lời bạn)

Chat model, cùng prompt:
→ "Sau khi peel da, bạn nên: 1. Tránh nắng..."
```

Base model **không trả lời câu hỏi**, nó **tiếp tục văn bản**. Khả năng nghe lời đến từ bước sau (Ngày 11).

### 1.4 Ba hệ quả quan trọng với công việc của bạn

**a) Knowledge cutoff.** Model chỉ biết những gì có trong dữ liệu train, đến một thời điểm. Hỏi về sự kiện sau đó → nó sẽ **bịa một cách trôi chảy**.

**b) Model KHÔNG biết dữ liệu riêng của bạn.** Bảng giá phòng khám, danh sách khách hàng, quy trình nội bộ — không có trong internet → model không biết. Ba cách đưa vào:

| Cách | Khi nào dùng | Chi phí | Cập nhật |
|---|---|---|---|
| **Nhồi vào prompt** | dữ liệu nhỏ, ít thay đổi | tốn token mỗi lượt | tức thì |
| **RAG** ⭐ | dữ liệu lớn, thay đổi thường xuyên | vừa | tức thì |
| **Fine-tuning** | cần định dạng/phong cách đặc thù | cao, cần dataset | phải train lại |

> Câu trả lời cho khách hàng: *"AI không biết về công ty anh/chị. Chúng ta phải đưa tài liệu cho nó — đó gọi là RAG, và đó chính là phần tôi xây."* Đây là cách bạn bán được dự án.

**c) Bias trong dữ liệu train sẽ lộ ra trong sản phẩm.** Dữ liệu chủ yếu tiếng Anh, văn hoá Âu Mỹ → model viết tiếng Việt đôi khi lơ lớ, xưng hô sai vai vế. Bạn phải chữa bằng prompt và few-shot (Ngày 23–24).

### 1.5 Scaling laws — tóm tắt

Chất lượng tăng theo hàm mũ khi tăng đồng thời: tham số, dữ liệu, tính toán. Nhưng **lợi ích giảm dần** và chi phí tăng phi tuyến. Xu hướng gần đây: model nhỏ được train tốt > model to train ẩu.

**Ứng dụng thực tế:** đừng mặc định chọn model lớn nhất. Ngày 70 bạn sẽ đo và thường thấy model nhỏ đủ dùng cho 80% tác vụ, rẻ hơn 5–10 lần.

---

## 2. Tài liệu (20 phút)

| Nguồn | Link | Bắt buộc |
|---|---|---|
| Karpathy — Intro to LLMs (1h, xem 0–30') | https://www.youtube.com/watch?v=zjkBMFhNj_g | ✅ |
| Anthropic — Model overview & cutoff | https://docs.anthropic.com/en/docs/about-claude/models/overview | ✅ |
| Chinchilla scaling laws (abstract) | https://arxiv.org/abs/2203.15556 | tuỳ chọn |

---

## 3. Thực hành (55 phút)

`exercises/day10/knowledge_probe.py` — dò xem model biết gì, không biết gì:

```python
"""Ngày 10: dò biên giới kiến thức của model."""
import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")


def ask(q: str, system: str = "") -> str:
    r = client.messages.create(
        model=MODEL, max_tokens=200, temperature=0,
        system=system or "Trả lời ngắn gọn.",
        messages=[{"role": "user", "content": q}],
    )
    return r.content[0].text.strip()


PROBES = {
    "kiến thức phổ thông": "Thủ đô của Việt Nam là gì?",
    "kiến thức chuyên môn": "Peel da bằng AHA khác BHA thế nào? 3 gạch đầu dòng.",
    "kiến thức RẤT mới": "Sự kiện công nghệ lớn nhất tháng trước là gì?",
    "dữ liệu riêng (KHÔNG tồn tại)": "Bảng giá dịch vụ của Phòng khám Thẩm mỹ Ánh Dương chi nhánh Quận 7 là bao nhiêu?",
    "tính toán": "Gói 10 buổi giá 12.000.000đ, đã dùng 6 buổi, hoàn 80%. Khách nhận lại bao nhiêu?",
}

HONEST = ("Trả lời ngắn gọn. Nếu bạn không chắc chắn hoặc không có thông tin, "
          "hãy nói rõ 'Tôi không có thông tin này' thay vì đoán.")

if __name__ == "__main__":
    for label, q in PROBES.items():
        print(f"\n{'='*66}\n[{label}]\nHỏi: {q}")
        print(f"\n-- Không hướng dẫn --\n{ask(q)}")
        print(f"\n-- Có yêu cầu trung thực --\n{ask(q, HONEST)}")
```

### Quan sát bắt buộc

1. Câu **"dữ liệu riêng"**: model có bịa ra bảng giá không? Chụp lại. Đây là bằng chứng bạn sẽ dùng khi thuyết phục khách hàng cần RAG.
2. System prompt yêu cầu trung thực có giảm bịa không? Giảm bao nhiêu phần trăm số câu?
3. Câu **tính toán**: model làm đúng không? Thử đổi số cho khó hơn (12.437.000đ, đã dùng 7/11 buổi, hoàn 83%).

---

## 4. Bài tập

**Bài 1 — Bản đồ kiến thức.** Soạn 12 câu hỏi chia 4 nhóm (phổ thông / chuyên ngành thẩm mỹ / sự kiện mới / dữ liệu nội bộ bịa ra). Hỏi model, lập bảng:

| Câu | Nhóm | Trả lời | Đúng/Sai/Bịa | Có thừa nhận không biết? |
|---|---|---|---|---|

Tính: **tỉ lệ bịa** = số câu bịa / tổng câu. Ngày 13 bạn sẽ tìm cách giảm con số này.

**Bài 2 — Quyết định kiến trúc.** Với mỗi loại dữ liệu của CareDesk-AI, chọn Prompt / RAG / Fine-tuning và giải thích:

| Dữ liệu | Cách đưa vào | Lý do |
|---|---|---|
| Bảng giá dịch vụ (đổi hàng quý) | | |
| Hồ sơ 3.000 khách hàng | | |
| Quy trình xử lý khiếu nại (30 trang) | | |
| Giọng văn thương hiệu | | |
| Lịch hẹn hôm nay | | |

**Bài 3 — Kịch bản bán hàng.** Viết 200 từ trả lời khách hàng hỏi: *"AI này có biết về phòng khám của tôi không? Nó học lúc nào?"* Viết cho người **không kỹ thuật**, không dùng từ "pretraining", "token", "embedding".

---

## 5. Quiz nhớ bài

```powershell
python quiz\quiz.py --day 10
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Giải thích được pretraining trong 3 câu
- [ ] Phân biệt được base model vs chat model
- [ ] Có bảng bản đồ kiến thức với tỉ lệ bịa cụ thể
- [ ] Điền xong bảng quyết định kiến trúc, mỗi dòng có lý do
- [ ] Bài 3 không dùng thuật ngữ kỹ thuật nào
- [ ] Quiz ≥ 80%
