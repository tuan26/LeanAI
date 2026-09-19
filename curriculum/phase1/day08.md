# NGÀY 8 — Context window

> Phase 1 · 25' lý thuyết — 15' tài liệu — 70' code — 10' note

## 🎯 Mục tiêu

Hiểu context window thật sự là gì, tự đo hiện tượng "lost in the middle", và rút ra quy tắc sắp xếp prompt.

---

## 1. Lý thuyết cốt lõi (25 phút)

### 1.1 Context window = toàn bộ trí nhớ của model tại một lần gọi

```
┌──────────── CONTEXT WINDOW (vd 200.000 token) ────────────┐
│ system prompt │ lịch sử hội thoại │ tài liệu RAG │ câu hỏi │ ← chỗ cho output
└────────────────────────────────────────────────────────────┘
```

**LLM không có trí nhớ giữa các lần gọi.** Mỗi request là một tờ giấy trắng. Cảm giác "ChatGPT nhớ bạn" chỉ là app gửi lại toàn bộ lịch sử mỗi lần.

Hệ quả trực tiếp: hội thoại càng dài → mỗi lượt càng đắt (Ngày 18 sẽ xử lý bằng tóm tắt).

### 1.2 Hai giới hạn khác nhau — đừng nhầm

| Giới hạn | Ý nghĩa |
|---|---|
| **Context window** | input + output ≤ N token |
| **Max output tokens** | riêng phần sinh ra ≤ M token (thường nhỏ hơn nhiều) |

Lỗi kinh điển: context 200k nhưng max output 8k → bảo model "viết lại toàn bộ tài liệu 50 trang" sẽ bị cắt giữa chừng.

### 1.3 Lost in the middle

Thông tin đặt **giữa** prompt dài bị model bỏ sót nhiều hơn hẳn thông tin ở **đầu** hoặc **cuối**.

```
độ chính xác
   ▲
   │ ●                                    ●
   │   ●                              ●
   │      ●                       ●
   │         ●   ●   ●   ●   ●
   └────────────────────────────────────►  vị trí thông tin trong prompt
     đầu              giữa              cuối
```

**Quy tắc sắp xếp prompt (nhớ suốt 90 ngày):**
```
1. system prompt / vai trò        ← đầu
2. tài liệu tham chiếu (ít nhất có thể)
3. ví dụ few-shot
4. CÂU HỎI + YÊU CẦU ĐỊNH DẠNG    ← cuối, ngay trước khi model sinh
```

### 1.4 Context dài không miễn phí

| Vấn đề | Chi tiết |
|---|---|
| Tiền | trả cho **mọi** input token, mỗi lượt |
| Latency | attention O(n²) (Ngày 6) |
| Chất lượng | nhiễu nhiều → model lạc hướng |
| Chú ý loãng | càng nhiều tài liệu, tài liệu đúng càng bị pha loãng |

> **Ngữ cảnh đúng thắng ngữ cảnh nhiều.** Đây là toàn bộ lý do RAG tồn tại.

### 1.5 Prompt caching

Nếu phần đầu prompt (system + tài liệu cố định) lặp lại giữa các request, nhiều provider cho phép cache nó — rẻ hơn đáng kể và nhanh hơn. Điều kiện: **phần cố định phải nằm ở đầu và không đổi**. Một lý do nữa để giữ đúng thứ tự mục 1.3.

---

## 2. Tài liệu (15 phút)

| Nguồn | Link | Bắt buộc |
|---|---|---|
| Anthropic — Context windows | https://docs.anthropic.com/en/docs/build-with-claude/context-windows | ✅ |
| Lost in the Middle (paper) | https://arxiv.org/abs/2307.03172 | ✅ đọc abstract + Figure 1 |
| Anthropic — Prompt caching | https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching | ✅ |

---

## 3. Thực hành (70 phút)

`exercises/day08/needle.py` — thí nghiệm "kim trong đống cỏ":

```python
"""Ngày 8: đo hiện tượng lost-in-the-middle bằng thí nghiệm needle-in-haystack."""
import os, time
import tiktoken
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
ENC = tiktoken.get_encoding("cl100k_base")

NEEDLE = "Mã ưu đãi nội bộ của phòng khám Quận 7 là VIP-7788."
FILLER = ("Phòng khám cam kết mang đến trải nghiệm chăm sóc tốt nhất cho khách hàng. "
          "Đội ngũ bác sĩ nhiều năm kinh nghiệm, trang thiết bị hiện đại. ")


def build_haystack(n_filler: int, needle_pos: float) -> str:
    """needle_pos: 0.0 = đầu, 0.5 = giữa, 1.0 = cuối."""
    parts = [FILLER] * n_filler
    idx = int(len(parts) * needle_pos)
    parts.insert(min(idx, len(parts)), NEEDLE + " ")
    return "".join(parts)


def ask(haystack: str) -> tuple[str, float, int]:
    prompt = (f"Đây là tài liệu nội bộ:\n\n{haystack}\n\n"
              "Câu hỏi: Mã ưu đãi nội bộ của phòng khám Quận 7 là gì? "
              "Chỉ trả lời mã, không giải thích.")
    t0 = time.time()
    r = client.messages.create(
        model=MODEL, max_tokens=50,
        messages=[{"role": "user", "content": prompt}],
    )
    return r.content[0].text.strip(), time.time() - t0, len(ENC.encode(prompt))


if __name__ == "__main__":
    print(f"{'filler':>7} {'vị trí':>7} {'token':>7} {'giây':>6}  kết quả")
    print("-" * 62)
    for n in (50, 300, 1200):
        for pos, label in ((0.0, "đầu"), (0.5, "giữa"), (1.0, "cuối")):
            ans, dt, ntok = ask(build_haystack(n, pos))
            ok = "OK " if "VIP-7788" in ans else "SAI"
            print(f"{n:>7} {label:>7} {ntok:>7} {dt:>6.2f}  {ok} {ans[:30]}")
```

### Quan sát bắt buộc

1. Với 1200 filler, vị trí **giữa** có sai không? Ghi lại.
2. Latency tăng thế nào theo số token? Ghi thành bảng.
3. Tính chi phí mỗi lần gọi ở mức 1200 filler (dùng `tokcount` ngày 4).

> Nếu model bạn dùng làm đúng cả 9 trường hợp: tăng `n` lên 5000 và thêm 3 needle giống nhau nhưng khác mã, hỏi mã của **chi nhánh Quận 3** — độ khó tăng vọt.

---

## 4. Bài tập

**Bài 1 — Bảng số liệu.** Chạy thí nghiệm trên với ít nhất 3 mức độ dài × 5 vị trí (0, 0.25, 0.5, 0.75, 1.0). Lập bảng độ chính xác + latency + chi phí, lưu `progress/notes/day08-needle.md`.

**Bài 2 — Ngân sách context.** Thiết kế ngân sách token cho một request CareDesk-AI (giới hạn 8.000 token input):
```
system prompt      : ___ token
hồ sơ khách hàng   : ___ token
lịch sử giao dịch  : ___ token
tài liệu RAG       : ___ token
câu hỏi + format   : ___ token
```
Viết 3 câu giải thích vì sao bạn chia như vậy.

**Bài 3 — Sửa prompt sai thứ tự.** Prompt dưới đây vi phạm quy tắc mục 1.3. Viết lại cho đúng và giải thích:
```
Câu hỏi: khách này có nên được gọi lại không?
[3000 token hồ sơ khách hàng]
Bạn là trợ lý phân tích khách hàng. Trả lời ngắn gọn, có lý do.
```

---

## 5. Quiz nhớ bài

```powershell
python quiz\quiz.py --day 8
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Chạy được needle test và có bảng số liệu thật
- [ ] Chỉ ra được ít nhất 1 trường hợp model bỏ sót thông tin
- [ ] Thuộc quy tắc sắp xếp prompt 4 tầng
- [ ] Làm xong ngân sách token Bài 2
- [ ] Quiz ≥ 80%
