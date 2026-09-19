# NGÀY 4 — Tokenization

> Phase 1 · 25' lý thuyết — 15' tài liệu — 70' code — 10' note

## 🎯 Mục tiêu

Hiểu token là gì, **đếm được token**, và biết vì sao tiếng Việt tốn token hơn tiếng Anh — điều này ảnh hưởng trực tiếp đến hoá đơn API của bạn.

---

## 1. Lý thuyết cốt lõi (25 phút)

### 1.1 Token không phải từ

Model không đọc chữ. Nó đọc **số**. Tokenizer là cầu nối:

```
"Chào chị Lan"  →  ["Ch", "ào", " ch", "ị", " Lan"]  →  [8421, 3119, 745, 2288, 19023]
     text                    tokens                            token IDs
```

Quy tắc kinh nghiệm:

| Ngôn ngữ | ~số ký tự / 1 token | 1000 từ ≈ |
|---|---|---|
| Tiếng Anh | 4 | ~1.300 token |
| **Tiếng Việt có dấu** | **1.5 – 2.5** | **~2.500–3.000 token** |
| Code | 3 | — |
| JSON có nhiều dấu ngoặc | 2 | — |

> **Tiếng Việt tốn gấp ~2× token so với tiếng Anh cho cùng nội dung.** Nghĩa là gấp đôi tiền, và chiếm gấp đôi context window. Đây là con số bạn phải nhớ khi định giá sản phẩm cho khách Việt Nam.

### 1.2 BPE — Byte Pair Encoding

Thuật toán tạo từ vựng, chạy 1 lần lúc train model:

```
1. Bắt đầu: từ vựng = 256 byte đơn lẻ
2. Đếm cặp ký tự liền nhau xuất hiện nhiều nhất trong corpus
3. Gộp cặp đó thành 1 token mới, thêm vào từ vựng
4. Lặp bước 2-3 cho đến khi đủ V token (vd 100.000)
```

Hệ quả: chuỗi phổ biến trong dữ liệu train → 1 token. Chuỗi hiếm → bị chẻ nhỏ. Vì corpus chủ yếu tiếng Anh nên tiếng Việt bị chẻ vụn.

### 1.3 Ba hệ quả thực chiến

**a) Model "không nhìn thấy" chữ cái.**
Hỏi "strawberry có mấy chữ r" → sai, vì model thấy `["straw","berry"]`, không thấy từng ký tự. Đây không phải model ngu, mà là giới hạn kiến trúc.

**b) Token quyết định tiền.**
```
Chi phí = (input_tokens × giá_input + output_tokens × giá_output) / 1.000.000
```
Đếm token TRƯỚC khi gọi API = kiểm soát được ngân sách.

**c) Token quyết định giới hạn context.**
Context 200k token với tiếng Việt ≈ 70.000–90.000 từ, không phải 200.000 từ.

### 1.4 Special token

| Token | Ý nghĩa |
|---|---|
| `<|endoftext|>` / `<|eot|>` | hết lượt / hết văn bản |
| `<|system|>`, `<|user|>`, `<|assistant|>` | đánh dấu vai (Ngày 17) |
| `<|tool_call|>` | báo hiệu gọi tool (Ngày 51) |

Chat template thực chất chỉ là việc chèn các special token này quanh nội dung của bạn. **Nếu người dùng nhập được các chuỗi này vào prompt → đó là một hướng prompt injection** (Ngày 28).

---

## 2. Tài liệu (15 phút)

| Nguồn | Link | Bắt buộc |
|---|---|---|
| OpenAI Tokenizer (chơi trực tiếp) | https://platform.openai.com/tokenizer | ✅ |
| Karpathy — Let's build the GPT Tokenizer (0–35') | https://www.youtube.com/watch?v=zduSFxRajkE | ✅ |
| Tiktoken repo | https://github.com/openai/tiktoken | tham khảo |

**Việc bắt buộc ở tokenizer web:** dán 3 chuỗi và ghi lại số token:
1. `"Xin chào, tôi muốn đặt lịch hẹn vào thứ Ba tuần sau."`
2. `"Hello, I would like to book an appointment next Tuesday."`
3. `{"customer":"Nguyễn Thị Lan","package":"Trị liệu da mặt"}`

---

## 3. Thực hành (70 phút)

```powershell
pip install tiktoken
mkdir exercises\day04
```

`exercises/day04/tokens.py`:

```python
"""Ngày 4: đếm token, đo chi phí, so sánh tiếng Việt vs tiếng Anh."""
import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")   # tokenizer họ GPT-4, đủ để ước lượng

# Giá tham khảo USD / 1 triệu token (tự cập nhật theo bảng giá hiện hành)
PRICES = {
    "small":  {"in": 0.80, "out": 4.00},
    "medium": {"in": 3.00, "out": 15.00},
    "large":  {"in": 15.00, "out": 75.00},
}


def count(text: str) -> int:
    return len(ENC.encode(text))


def show_tokens(text: str, limit: int = 30) -> None:
    ids = ENC.encode(text)
    pieces = [ENC.decode([i]) for i in ids[:limit]]
    print(f"  {len(ids)} token: {pieces}")


def cost(in_tokens: int, out_tokens: int, tier: str = "medium") -> float:
    p = PRICES[tier]
    return (in_tokens * p["in"] + out_tokens * p["out"]) / 1_000_000


def ratio_report(vi: str, en: str) -> None:
    tv, te = count(vi), count(en)
    print(f"  VI: {tv:>4} token | {len(vi):>4} ký tự | {len(vi)/tv:.2f} ký tự/token")
    print(f"  EN: {te:>4} token | {len(en):>4} ký tự | {len(en)/te:.2f} ký tự/token")
    print(f"  => Tiếng Việt tốn gấp {tv/te:.2f}x")


if __name__ == "__main__":
    vi = "Xin chào, tôi muốn đặt lịch hẹn vào thứ Ba tuần sau tại chi nhánh Quận 1."
    en = "Hello, I would like to book an appointment next Tuesday at the District 1 branch."

    print("--- Cách token được cắt ---")
    show_tokens(vi)
    show_tokens(en)

    print("\n--- Tỉ lệ VI/EN ---")
    ratio_report(vi, en)

    print("\n--- Chi phí 1 request chăm sóc khách ---")
    system = "Bạn là trợ lý chăm sóc khách hàng của spa. Viết tin nhắn Zalo thân thiện, dưới 60 từ."
    context = "Khách: Nguyễn Thị Lan. Gói: Trị liệu da mặt 10 buổi, còn 4 buổi. Lần cuối: 112 ngày trước."
    in_tok = count(system) + count(context)
    out_tok = 120
    c = cost(in_tok, out_tok)
    print(f"  input {in_tok} + output {out_tok} token = ${c:.6f} ≈ {c*25000:.1f} VNĐ")
    print(f"  1.000 khách/tháng  = ${c*1000:.2f}")
    print(f"  10 clinic × 1.000  = ${c*10000:.2f}/tháng")

    print("\n--- Vì sao model đếm chữ cái sai ---")
    show_tokens("strawberry")
    show_tokens("Nguyễn")
```

### Quan sát bắt buộc

1. Chữ `"Nguyễn"` bị cắt thành mấy token? Ghi lại.
2. Chi phí 10 clinic/tháng là bao nhiêu? Đây là **biên lợi nhuận** của CareDesk-AI.
3. Thử `show_tokens` với chuỗi có emoji và với JSON — cái nào tốn hơn?

---

## 4. Bài tập

**Bài 1 — Công cụ đếm token CLI.**
Viết `exercises/day04/tokcount.py` nhận đường dẫn file, in ra: số token, số ký tự, tỉ lệ, chi phí ước tính ở 3 tier. Test bằng chính file `curriculum/phase1/day01.md`.
*Tiêu chí PASS:* chạy `python tokcount.py curriculum/phase1/day01.md` ra kết quả hợp lý.

**Bài 2 — Bài toán định giá.**
Một phòng khám có 3.000 khách. Mỗi tháng quét toàn bộ để tìm cơ hội, mỗi khách tốn 400 token input + 150 token output.
a) Chi phí/tháng ở tier `small` và `medium`?
b) Nếu bạn bán 2.000.000 VNĐ/tháng/phòng khám, biên lợi nhuận gộp là bao nhiêu %?
c) Cách nào giảm 50% chi phí mà không giảm chất lượng? (gợi ý: lọc bằng SQL trước khi gọi LLM — Ngày 1 mục 1.4)

**Bài 3 — Prompt tiết kiệm.**
Viết lại system prompt dưới đây cho ngắn hơn ≥ 40% token nhưng giữ nguyên ý:
```
Bạn là một trợ lý ảo chuyên nghiệp làm việc cho một chuỗi phòng khám thẩm mỹ tại Việt Nam.
Nhiệm vụ của bạn là giúp nhân viên chăm sóc khách hàng viết những tin nhắn thật sự thân thiện,
lịch sự, không gây cảm giác làm phiền, và luôn luôn phải xưng hô đúng mực với khách hàng.
```
Đo bằng `count()` trước và sau.

---

## 5. Quiz nhớ bài

```powershell
python quiz\quiz.py --day 4
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `tokens.py` chạy được, giải thích được từng con số
- [ ] `tokcount.py` hoạt động trên file bất kỳ
- [ ] Trả lời đủ 3 ý của Bài 2 bằng số cụ thể
- [ ] Bài 3 giảm ≥ 40% token
- [ ] Quiz ≥ 80%

> Từ hôm nay, mỗi lần viết prompt bạn phải có phản xạ: *"cái này bao nhiêu token?"*
