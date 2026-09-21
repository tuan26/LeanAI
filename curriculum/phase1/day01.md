# NGÀY 1 — AI vs ML vs DL vs LLM

> Phase 1 · Nhịp: 30' lý thuyết — 20' tài liệu — 60' code — 10' note

## 🎯 Mục tiêu

Kết thúc hôm nay bạn phải **nói được trong 60 giây** cho một khách hàng không kỹ thuật: AI, Machine Learning, Deep Learning, LLM khác nhau chỗ nào, và khi nào **không** nên dùng LLM.

Đây không phải kiến thức trang trí. Nó quyết định bạn có bán sai giải pháp cho khách hàng hay không.

---

## 1. Lý thuyết cốt lõi (30 phút)

### 1.1 Bốn vòng tròn lồng nhau

```
┌─────────────────────────────────────────────┐
│ AI — mọi hệ thống bắt chước hành vi thông   │
│      minh (kể cả if/else và cây quyết định) │
│  ┌───────────────────────────────────────┐  │
│  │ ML — học quy luật TỪ DỮ LIỆU,         │  │
│  │      không phải từ luật người viết    │  │
│  │  ┌─────────────────────────────────┐  │  │
│  │  │ DL — ML dùng mạng neuron nhiều  │  │  │
│  │  │      lớp, tự học đặc trưng      │  │  │
│  │  │  ┌───────────────────────────┐  │  │  │
│  │  │  │ LLM — DL kiến trúc        │  │  │  │
│  │  │  │ Transformer, học trên      │  │  │  │
│  │  │  │ lượng text khổng lồ        │  │  │  │
│  │  │  └───────────────────────────┘  │  │  │
│  │  └─────────────────────────────────┘  │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### 1.2 Khác biệt cốt lõi: ai viết ra quy luật?

| | Ai tạo ra quy luật | Ví dụ trong phòng khám |
|---|---|---|
| **Lập trình truyền thống** | Con người viết `if...else` | "Nếu khách chưa đến sau 90 ngày → gửi SMS" |
| **ML** | Thuật toán học từ dữ liệu lịch sử | Học từ 10.000 khách cũ để dự đoán ai sẽ quay lại |
| **DL** | Mạng neuron tự học cả đặc trưng | Nhận diện khuôn mặt khách từ ảnh, không ai định nghĩa "mắt" là gì |
| **LLM** | Học phân phối xác suất của ngôn ngữ | Viết tin nhắn chăm sóc khách bằng tiếng Việt tự nhiên |

### 1.3 LLM thực chất làm gì?

Chỉ một việc duy nhất: **đoán token tiếp theo**.

```
"Chị Lan chưa quay lại spa từ tháng"  →  P("3")=0.21  P("6")=0.18  P("trước")=0.15 ...
```

Tất cả những thứ trông như "suy luận", "sáng tạo", "hiểu" đều nổi lên (emergent) từ việc đoán token này khi mô hình đủ lớn và dữ liệu đủ nhiều. Ghi nhớ điều này — nó giải thích **mọi** hành vi kỳ lạ của LLM sau này, đặc biệt là hallucination (Ngày 13).

### 1.4 Ba câu hỏi trước khi dùng LLM cho một bài toán

Đây là khung tôi muốn bạn dùng suốt 90 ngày:

1. **Bài toán có một đáp án đúng xác định được bằng luật không?**
   → Có: dùng code thường. Đừng dùng LLM tính tiền, tính tuổi, tính ngày quá hạn.
2. **Đầu vào có phải ngôn ngữ tự nhiên / phi cấu trúc không?**
   → Không: có thể ML cổ điển rẻ hơn 1000 lần.
3. **Sai một chút có chết ai không?**
   → Có: bắt buộc human-in-the-loop (Ngày 61).

> **Quy tắc vàng:** LLM giỏi *biến đổi ngôn ngữ*, dở *tính toán chính xác*. Luôn để code làm toán, để LLM làm chữ.

### 1.5 Ứng dụng vào CareDesk-AI (capstone)

| Thành phần | Nên dùng gì | Vì sao |
|---|---|---|
| Phát hiện khách quá hạn tái khám | **SQL / rule** | Chính xác tuyệt đối, chi phí ~0 |
| Ước tính giá trị cơ hội | **Rule + ML sau này** | Cần con số ổn định, kiểm toán được |
| Giải thích "vì sao khách này" | **LLM** | Cần diễn đạt tự nhiên cho nhân viên |
| Soạn tin nhắn Zalo | **LLM** | Đúng thế mạnh: sinh ngôn ngữ |
| Quyết định có gửi hay không | **Con người** | Rủi ro thương hiệu |

Đây chính là kiến trúc bạn sẽ build ở ngày 82–87. Hôm nay bạn đã hiểu *vì sao* nó được chia như vậy.

---

## 2. Tài liệu (20 phút)

| Nguồn | Link | Thời lượng | Bắt buộc |
|---|---|---|---|
| 3Blue1Brown — But what is a neural network? | https://www.youtube.com/watch?v=aircAruvnKk | 19' | ✅ (xem 0:00–8:00 hôm nay, phần còn lại Ngày 2) |
| Anthropic — What is a LLM? | https://docs.anthropic.com/en/docs/about-claude/models/overview | 10' | ✅ |
| Google — Intro to ML (phần "Framing") | https://developers.google.com/machine-learning/intro-to-ml | 10' | tuỳ chọn |

**Cách đọc:** không đọc để hiểu hết. Đọc để trả lời được 5 câu quiz cuối bài.

---

## 3. Thực hành (60 phút)

Hôm nay chưa gọi API. Mục tiêu: **cảm nhận** ranh giới giữa rule và học máy.

### Bước 1 — Tạo file

```powershell
mkdir exercises\day01
notepad exercises\day01\rule_vs_ml.py
```

### Bước 2 — Code (gõ tay, đừng copy)

```python
"""Ngày 1: cùng một bài toán, ba cách giải khác nhau."""

# ---------- CÁCH 1: LUẬT (con người viết quy luật) ----------
def is_overdue_rule(days_since_last_visit: int, package_cycle_days: int) -> bool:
    """Khách quá hạn tái khám? Quy luật do con người định nghĩa."""
    return days_since_last_visit > package_cycle_days * 1.2


# ---------- CÁCH 2: HỌC TỪ DỮ LIỆU (ML rất thô sơ) ----------
history = [
    # (số ngày kể từ lần cuối, đã quay lại?)
    (30, True), (45, True), (60, True), (75, True),
    (95, False), (110, False), (130, False), (200, False),
]

def learn_threshold(data):
    """Tự tìm ngưỡng tốt nhất từ dữ liệu, không ai nói trước ngưỡng là bao nhiêu."""
    best_t, best_acc = 0, 0.0
    for t in range(0, 250, 5):
        correct = sum((d <= t) == returned for d, returned in data)
        acc = correct / len(data)
        if acc > best_acc:
            best_t, best_acc = t, acc
    return best_t, best_acc


# ---------- CÁCH 3: LLM (sinh ngôn ngữ, chưa gọi API hôm nay) ----------
def draft_message_template(name: str, days: int) -> str:
    """Hôm nay dùng template. Ngày 16 ta sẽ thay bằng LLM thật và so sánh."""
    return f"Chào chị {name}, đã {days} ngày chị chưa ghé spa..."


if __name__ == "__main__":
    print("--- RULE ---")
    print("120 ngày, chu kỳ 60:", is_overdue_rule(120, 60))

    print("\n--- HỌC TỪ DỮ LIỆU ---")
    t, acc = learn_threshold(history)
    print(f"Ngưỡng học được: {t} ngày (độ chính xác {acc:.0%})")
    print("Lưu ý: KHÔNG ai nói cho máy biết con số này. Nó tự tìm.")

    print("\n--- SINH NGÔN NGỮ ---")
    print(draft_message_template("Lan", 120))
```

### Bước 3 — Chạy và quan sát

```powershell
python exercises\day01\rule_vs_ml.py
```

### Bước 4 — Thí nghiệm bắt buộc

Thêm vào `history` một khách bất thường: `(35, False)` (mới 35 ngày nhưng không quay lại).
Chạy lại. **Ngưỡng học được thay đổi thế nào?**

Đây chính là bài học quan trọng nhất hôm nay: *ML phụ thuộc dữ liệu — dữ liệu bẩn thì mô hình bẩn, và không có thông báo lỗi nào cả.*

---

## 4. Bài tập

### Bài 1 — Phân loại 10 bài toán (20 phút)

Với mỗi bài toán dưới đây, ghi vào `progress/journal.md`: chọn **Rule / ML / DL / LLM** và **một câu** lý do.

| # | Bài toán |
|---|---|
| 1 | Tính tiền còn lại trong gói liệu trình của khách |
| 2 | Dự đoán khách nào sẽ bỏ không quay lại trong 30 ngày tới |
| 3 | Tóm tắt 200 phản hồi khách hàng thành 5 chủ đề chính |
| 4 | Nhận diện khách quen qua camera ở cửa |
| 5 | Kiểm tra số điện thoại có đúng định dạng VN không |
| 6 | Trả lời câu hỏi "chính sách hoàn tiền của spa thế nào?" từ tài liệu nội bộ |
| 7 | Chấm điểm mức độ hài lòng từ câu bình luận tiếng Việt |
| 8 | Gợi ý giờ hẹn trống gần nhất |
| 9 | Viết caption Facebook cho chương trình khuyến mãi |
| 10 | Phát hiện giao dịch thanh toán bất thường |

**Đáp án tham khảo** nằm ở cuối file — chỉ mở sau khi làm xong.

### Bài 2 — Một trang note (20 phút)

Viết `progress/notes/day01.md`, đúng cấu trúc:

```markdown
# Ngày 1 — AI vs ML vs DL vs LLM
## Định nghĩa 1 câu (tự viết, KHÔNG copy)
- AI:
- ML:
- DL:
- LLM:
## Khác biệt then chốt
## LLM thực chất làm gì
## 3 câu hỏi trước khi dùng LLM
## Áp dụng vào CareDesk-AI
## Điều tôi vẫn chưa hiểu
```

Mục cuối cùng là **bắt buộc** và không được để trống. Nếu bạn nghĩ mình hiểu hết thì bạn chưa hiểu gì.

### Bài 3 — Giải thích 60 giây (10 phút)

Bật ghi âm điện thoại, giải thích 4 khái niệm cho "chủ spa 45 tuổi không biết công nghệ". Nghe lại. Nếu bạn dùng từ "thuật toán", "mô hình", "tham số" → làm lại, giải thích bằng ví dụ đời thường.

---

## 5. Quiz nhớ bài

```powershell
python quiz\quiz.py --day 1
```

5 câu. Cần **≥ 80%** mới được sang Ngày 2. Sai câu nào → đọc lại đúng mục đó rồi chạy lại.

---

## 6. Tiêu chí PASS/FAIL

- [ ] Chạy được `rule_vs_ml.py` và giải thích được vì sao ngưỡng thay đổi khi thêm dữ liệu bẩn
- [ ] Phân loại đúng ≥ 8/10 bài toán ở Bài 1
- [ ] Có file `progress/notes/day01.md` đủ 6 mục, phần "chưa hiểu" không trống
- [ ] Quiz ≥ 80%
- [ ] Nói được 60 giây không dùng thuật ngữ

**FAIL** nếu thiếu bất kỳ mục nào → làm lại hôm sau, không học Ngày 2.

---

## 7. Sổ tay

```powershell
git add . ; git commit -m "day 01: AI vs ML vs DL vs LLM"
```

---

<details markdown="1">
<summary>Đáp án Bài 1 (chỉ mở sau khi tự làm)</summary>

| # | Đáp án | Lý do |
|---|---|---|
| 1 | **Rule** | Phép trừ. Dùng LLM ở đây là sai lầm kinh điển — nó sẽ tính sai và bạn không biết |
| 2 | **ML** | Dự đoán từ mẫu lịch sử, đầu vào có cấu trúc |
| 3 | **LLM** | Văn bản phi cấu trúc, cần hiểu ngữ nghĩa |
| 4 | **DL** | Thị giác máy tính, đặc trưng ảnh không thể viết tay |
| 5 | **Rule** | Regex. Chính xác 100%, chi phí 0 |
| 6 | **LLM + RAG** | Đây chính là Project #2 của bạn (Ngày 50) |
| 7 | **LLM** (hoặc ML cổ điển nếu cần rẻ + nhanh) | Sentiment tiếng Việt |
| 8 | **Rule** | Truy vấn lịch trống, thuần logic |
| 9 | **LLM** | Sinh ngôn ngữ sáng tạo |
| 10 | **ML** | Phát hiện bất thường trên dữ liệu số |

Nếu bạn chọn LLM cho câu 1, 5, 8 → đọc lại mục 1.4. Đây là lỗi đắt tiền nhất của người mới.
</details>
