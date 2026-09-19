# NGÀY 9 — Temperature & sampling

> Phase 1 · 25' lý thuyết — 15' tài liệu — 70' code — 10' note

## 🎯 Mục tiêu

Biết chính xác temperature/top_p làm gì, và có **bảng tra** để chọn tham số cho từng loại tác vụ trong sản phẩm.

---

## 1. Lý thuyết cốt lõi (25 phút)

### 1.1 Model xuất ra phân phối, không phải một chữ

Sau lớp cuối (Ngày 3), model có điểm số (logits) cho **mọi** token trong từ vựng. Softmax biến thành xác suất:

```
"Chị Lan chưa quay lại spa từ tháng ..."
   "3"      0.28
   "6"      0.21
   "trước"  0.15
   "này"    0.09
   ... 128.000 token khác
```

**Sampling** là bước chọn ra một token. Đây là bước duy nhất có tính ngẫu nhiên.

### 1.2 Temperature — chia logits trước khi softmax

```
p_i = softmax(logit_i / T)
```

| T | Hiệu ứng | Trực giác |
|---|---|---|
| 0 | luôn chọn token cao nhất (greedy) | máy tính |
| 0.3 | rất bám phân phối gốc | thư ký cẩn thận |
| 0.7 | cân bằng | người viết bình thường |
| 1.0 | đúng phân phối gốc | tự nhiên |
| 1.5+ | san phẳng phân phối | người say rượu |

Quan trọng: **T thấp không làm model đúng hơn về mặt sự thật**. Nó chỉ làm model **nhất quán** hơn. Một model tin chắc điều sai thì T=0 sẽ sai một cách rất tự tin.

### 1.3 Top-k và top-p (nucleus)

| Chiến lược | Cách làm | Nhược điểm |
|---|---|---|
| **top-k** | chỉ giữ k token xác suất cao nhất | k cố định không phù hợp mọi ngữ cảnh |
| **top-p** | giữ các token cho đến khi tổng xác suất ≥ p | thích nghi theo ngữ cảnh — **nên dùng** |

```
top_p = 0.9:  giữ "3"(0.28) "6"(0.21) "trước"(0.15) ... cho đến khi cộng đủ 0.90
```

> **Quy tắc:** chỉnh **một trong hai**, không chỉnh cả temperature lẫn top_p cùng lúc. Chỉnh cả hai làm bạn không biết cái nào gây ra thay đổi.

### 1.4 Bảng tra cho sản phẩm — dán lên tường

| Tác vụ | temperature | Lý do |
|---|---|---|
| Trích xuất dữ liệu → JSON | **0** | cần lặp lại được, cần parse được |
| Phân loại / gán nhãn | **0** | cần nhất quán, cần đánh giá được |
| Trả lời từ tài liệu (RAG) | **0 – 0.2** | bám nguồn, chống bịa |
| Tool calling / agent | **0 – 0.2** | quyết định phải ổn định |
| Tóm tắt | 0.2 – 0.4 | hơi linh hoạt về diễn đạt |
| Soạn tin nhắn khách hàng | **0.6 – 0.8** | cần tự nhiên, không máy móc |
| Brainstorm ý tưởng | 0.9 – 1.1 | cần đa dạng |

Trong CareDesk-AI bạn sẽ dùng **T=0 cho phát hiện cơ hội** và **T=0.7 cho soạn tin nhắn**. Cùng một sản phẩm, hai tham số khác nhau — đó là dấu hiệu của kỹ sư, không phải người dùng.

### 1.5 T=0 không có nghĩa là hoàn toàn tất định

Ngay cả T=0, kết quả vẫn có thể lệch nhẹ giữa các lần gọi do: phép tính dấu phẩy động trên GPU, batching phía server, cập nhật model. **Đừng bao giờ thiết kế hệ thống giả định output giống hệt nhau 100%.** Luôn validate (Ngày 30).

---

## 2. Tài liệu (15 phút)

| Nguồn | Link | Bắt buộc |
|---|---|---|
| Anthropic — temperature parameter | https://docs.anthropic.com/en/api/messages | ✅ |
| How to sample from LLMs (Hugging Face blog) | https://huggingface.co/blog/how-to-generate | ✅ |

---

## 3. Thực hành (70 phút)

`exercises/day09/sampling.py`:

```python
"""Ngày 9: đo ảnh hưởng thật của temperature."""
import os
from collections import Counter

import numpy as np
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")


# --- Phần A: mô phỏng temperature bằng numpy (không tốn tiền) ---
def apply_temperature(logits, T):
    if T == 0:
        p = np.zeros_like(logits); p[np.argmax(logits)] = 1.0; return p
    z = logits / T
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def top_p_filter(probs, p=0.9):
    order = np.argsort(probs)[::-1]
    cum = np.cumsum(probs[order])
    keep = order[: np.searchsorted(cum, p) + 1]
    out = np.zeros_like(probs)
    out[keep] = probs[keep]
    return out / out.sum()


# --- Phần B: gọi model thật ---
def generate(prompt: str, temperature: float, n: int = 5) -> list[str]:
    outs = []
    for _ in range(n):
        r = client.messages.create(
            model=MODEL, max_tokens=60, temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        outs.append(r.content[0].text.strip())
    return outs


if __name__ == "__main__":
    tokens = ["3", "6", "trước", "này", "rồi"]
    logits = np.array([3.0, 2.7, 2.3, 1.8, 1.2])

    print("=== Temperature làm gì với phân phối ===")
    print(f"{'T':>5} " + " ".join(f"{t:>8}" for t in tokens))
    for T in (0.0, 0.3, 0.7, 1.0, 1.5, 2.0):
        p = apply_temperature(logits, T)
        print(f"{T:>5} " + " ".join(f"{x:>8.3f}" for x in p))

    print("\n=== top_p = 0.9 (tại T=1.0) ===")
    p = top_p_filter(apply_temperature(logits, 1.0), 0.9)
    print(" ".join(f"{t}={x:.3f}" for t, x in zip(tokens, p)))

    print("\n=== Model thật: tính lặp lại ===")
    prompt_fact = ("Gói trị liệu 10 buổi giá 12.000.000đ, khách đã dùng 6 buổi. "
                   "Còn lại bao nhiêu tiền? Chỉ trả lời số.")
    prompt_creative = "Viết 1 câu mở đầu tin nhắn Zalo mời khách quay lại spa. Chỉ 1 câu."

    for label, prompt in (("SỰ THẬT", prompt_fact), ("SÁNG TẠO", prompt_creative)):
        for T in (0.0, 1.0):
            outs = generate(prompt, T)
            uniq = len(set(outs))
            print(f"\n[{label}] T={T}: {uniq}/5 kết quả khác nhau")
            for o in Counter(outs).most_common(3):
                print(f"   x{o[1]} {o[0][:70]}")
```

### Quan sát bắt buộc

1. Ở prompt **SỰ THẬT**, T=1.0 có cho ra đáp án khác nhau không? Nếu có → đó chính là lý do bài toán tính tiền phải để code làm, không để LLM (Ngày 1).
2. Ở prompt **SÁNG TẠO**, T=0 cho ra 5 câu giống hệt → tin nhắn gửi 1000 khách sẽ giống nhau y hệt. Khách sẽ nhận ra.
3. Ghi lại: số kết quả khác nhau ở từng cấu hình.

---

## 4. Bài tập

**Bài 1 — Bảng thực nghiệm.** Chạy `generate` với T ∈ {0, 0.3, 0.7, 1.0, 1.5} × 2 loại prompt × 5 lần. Lập bảng: `T | số output khác nhau | chất lượng (bạn tự chấm 1-5) | nhận xét`. Lưu `progress/notes/day09-temperature.md`.

**Bài 2 — Chọn tham số cho CareDesk-AI.** Điền bảng, mỗi dòng kèm 1 câu lý do:

| Chức năng | T | top_p | Lý do |
|---|---|---|---|
| Phân loại loại cơ hội doanh thu | | | |
| Ước tính giá trị cơ hội | | | |
| Giải thích "vì sao khách này" | | | |
| Soạn tin nhắn Zalo | | | |
| Trả lời câu hỏi từ tài liệu nội bộ | | | |

**Bài 3 — Bẫy.** Một đồng nghiệp nói: *"Cứ để temperature = 0 thì AI sẽ không bịa nữa."* Viết 5 câu phản biện, có dẫn chứng từ thí nghiệm của bạn.

---

## 5. Quiz nhớ bài

```powershell
python quiz\quiz.py --day 9
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Giải thích được temperature bằng công thức **và** bằng lời
- [ ] Phân biệt được top-k và top-p
- [ ] Có bảng số liệu thật từ Bài 1
- [ ] Điền xong bảng tham số CareDesk-AI có lý do
- [ ] Phản biện được câu "T=0 thì hết bịa"
- [ ] Quiz ≥ 80%
