# NGÀY 7 — Ôn tập tuần 1

> Phase 1 · Không học kiến thức mới. Hôm nay để **kiến thức đóng rắn**.

## 🎯 Mục tiêu

Viết được bài "LLM hoạt động thế nào?" từ trí nhớ, và vá mọi lỗ hổng của 6 ngày qua.

---

## 1. Kiểm tra trí nhớ trước (30 phút)

Làm **trước khi** đọc lại bất cứ thứ gì:

```powershell
python quiz\quiz.py --exam 1 6
```

Ghi lại điểm: `____/30`

| Điểm | Hành động |
|---|---|
| ≥ 90% | Xuất sắc. Làm phần 2–4, kết thúc sớm |
| 75–89% | Bình thường. Đọc lại đúng những mục sai |
| 60–74% | Đọc lại toàn bộ ngày có câu sai + làm lại bài tập ngày đó |
| < 60% | **Dừng lộ trình.** Dành cả cuối tuần học lại tuần 1. Không sang Ngày 8 |

```powershell
python quiz\quiz.py --weak     # xem 10 câu yếu nhất
```

---

## 2. Bài viết bắt buộc (60 phút)

Viết `progress/notes/week1-how-llm-works.md`, **1200–1800 từ**, không mở tài liệu trong lúc viết (mở sau để sửa).

Dàn ý bắt buộc:

```markdown
# LLM hoạt động thế nào?

## 1. Bối cảnh
AI / ML / DL / LLM khác nhau ở đâu — và vì sao phân biệt được điều này
giúp tôi không bán sai giải pháp cho khách hàng.

## 2. Nền tảng: mạng neuron
- Neuron = w·x + b rồi qua hàm phi tuyến
- "Tham số" là gì, "học" là gì
- Vì sao cần phi tuyến (ví dụ XOR tôi đã tự chạy)

## 3. Text vào model bằng cách nào
- Tokenization, BPE
- Số liệu tôi tự đo: tiếng Việt tốn gấp ___ lần tiếng Anh
- Hệ quả tiền bạc

## 4. Model hiểu ngữ nghĩa bằng cách nào
- Embedding, cosine similarity
- Số liệu tôi tự đo: "có bảo hành" vs "không bảo hành" = ___
- Giới hạn của embedding

## 5. Attention — trái tim của Transformer
- Q, K, V bằng ví dụ của riêng tôi
- Causal mask
- Chi phí O(n²) — số liệu tôi tự đo

## 6. Ghép lại: kiến trúc Transformer
- Sơ đồ từ trí nhớ
- Vai trò từng khối
- Vì sao output token đắt hơn input token

## 7. Quay lại thực tế
Trong CareDesk-AI, phần nào nên dùng LLM, phần nào tuyệt đối không.
Vì sao — dựa trên những gì tôi vừa viết ở trên.

## 8. Ba điều tôi vẫn chưa chắc
```

**Quy tắc chấm:** mỗi mục có số liệu phải là **số bạn tự chạy ra**, không phải số copy từ file bài học. Nếu chưa có số → chạy lại code ngày đó.

---

## 3. Vá lỗ hổng (20 phút)

Xem lại `progress/notes/dayXX.md` mục "Điều tôi vẫn chưa hiểu" của 6 ngày. Với mỗi câu:
- Tự trả lời được rồi? → gạch bỏ, ghi câu trả lời.
- Chưa? → tra cứu 10 phút. Vẫn chưa? → ghi vào `progress/open-questions.md`, quay lại sau Phase 2. Không sa lầy.

---

## 4. Tổng kết số liệu tuần 1 (10 phút)

Điền bảng vào cuối bài viết:

| Chỉ số tôi tự đo | Giá trị |
|---|---|
| Tỉ lệ token VI/EN | |
| Chi phí 1 tin nhắn chăm sóc khách (USD) | |
| Chi phí 10 clinic × 1000 khách/tháng | |
| Similarity "có bảo hành" vs "không bảo hành" | |
| Recall@1 trên KB mini của tôi | |
| Thời gian attention n=1024 vs n=2048 | |
| Số tham số model 7B ước lượng | |
| VRAM fp16 cho 70B | |

Bảng này là **bằng chứng bạn học thật**. Nó sẽ vào portfolio.

---

## 5. Checklist tuần 1

- [ ] Giải thích được AI/ML/DL/LLM trong 60 giây, không thuật ngữ
- [ ] Viết được forward pass của một neuron trên giấy
- [ ] Vẽ được sơ đồ Transformer từ trí nhớ
- [ ] Đếm được token và tính được chi phí bất kỳ prompt nào
- [ ] Giải thích được embedding và 2 giới hạn của nó
- [ ] Viết được công thức attention và giải thích từng thành phần
- [ ] Biết khi nào **không** nên dùng LLM
- [ ] 7 commit trong git
- [ ] Bài viết ≥ 1200 từ, mọi số liệu tự đo

---

## 6. Nhìn trước tuần 2

Ngày 8–13 là "hành vi model": context, sampling, pretraining, instruction tuning, RLHF, hallucination.
Ngày 14 là mini project đầu tiên — **AI Explanation Engine** chạy được.

Từ Ngày 8 bạn bắt đầu tốn tiền API. Kiểm tra key hoạt động ngay hôm nay:

```powershell
python quiz\quiz.py --doctor
```
