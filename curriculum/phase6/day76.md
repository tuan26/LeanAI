# NGÀY 76 — Domain & problem framing

> Phase 6 · 60' nghiên cứu — 60' viết PRD

## 🎯 Mục tiêu

PRD 2 trang cho CareDesk-AI. Không code. **Nếu bài toán sai, 14 ngày còn lại là lãng phí.**

---

## 1. Việc phải làm

### Bước 1 — Kiểm chứng bài toán (60 phút)

Nói chuyện với **ít nhất 1 chủ spa/phòng khám thật** (gọi điện, nhắn tin, hoặc gặp). Hỏi 7 câu:

```
1. Mỗi tháng có bao nhiêu khách mua gói rồi không dùng hết?
2. Hiện tại ai theo dõi việc đó? Bằng cách nào?
3. Lần cuối chị nhắc khách quay lại là khi nào? Bằng cách gì?
4. Một khách quay lại mang về bao nhiêu doanh thu trung bình?
5. Điều gì khiến chị KHÔNG làm việc nhắc khách này thường xuyên?
6. Nếu có hệ thống tự phát hiện và soạn sẵn tin nhắn, chị có dùng không?
7. Chị sẵn sàng trả bao nhiêu một tháng cho việc đó?
```

Ghi lại **nguyên văn** câu trả lời. Câu 5 và 7 quan trọng nhất.

> Nếu không tiếp cận được người thật: tìm 5 bài đăng/nhóm Facebook của chủ spa nói về vấn đề giữ chân khách, trích dẫn. Nhưng hãy cố gắng nói chuyện thật — dữ liệu từ một cuộc gọi hơn mười giả định.

### Bước 2 — Viết PRD (60 phút)

`projects/capstone-caredesk-ai/PRD.md`:

```markdown
# CareDesk-AI — PRD v1.0

## 1. Vấn đề
<Mô tả bằng số liệu thật hoặc trích dẫn từ người dùng, không phải giả định của bạn>

Ví dụ: "Phòng khám X có ~3.000 khách. Ước tính __% mua gói không dùng hết.
Giá trị tồn đọng ước tính __đ/tháng. Hiện không ai theo dõi vì __."

## 2. Ai dùng sản phẩm
| Vai trò | Họ làm gì hiện nay | Đau ở đâu | Sản phẩm giúp gì |
|---|---|---|---|
| Lễ tân | | | |
| Quản lý phòng khám | | | |
| Chủ chuỗi | | | |

## 3. Phạm vi v1 (15 ngày)
### CÓ
- Phát hiện 5 loại cơ hội doanh thu từ dữ liệu khách
- Giải thích vì sao, có dẫn chứng số liệu
- Soạn tin nhắn Zalo/SMS
- Người duyệt trước khi gửi
- Dashboard 5 chỉ số

### KHÔNG CÓ (ghi rõ để không bị cuốn)
- Tích hợp phần mềm quản lý hiện có
- Tự động gửi không cần duyệt
- Chatbot trả lời khách
- Ứng dụng di động
- Thanh toán

## 4. Chỉ số thành công
| Chỉ số | Mục tiêu v1 |
|---|---|
| Precision phát hiện cơ hội | ≥ 0.85 |
| Tỉ lệ nhân viên duyệt thẳng (không sửa) | ≥ 70% |
| Thời gian từ đăng nhập đến tin nhắn đầu tiên | < 3 phút |
| Chi phí AI / phòng khám / tháng | < 400.000đ |
| Tỉ lệ rò rỉ dữ liệu giữa phòng khám | 0 |

## 5. Rủi ro và cách giảm
| Rủi ro | Mức | Cách giảm |
|---|---|---|
| AI soạn tin sai số liệu | cao | số liệu do code chèn, guardrail chặn số lạ |
| Làm phiền khách | cao | giới hạn tần suất, danh sách chặn, người duyệt |
| Dữ liệu phòng khám lẫn nhau | rất cao | tenant_id mọi tầng + test tự động |
| Chi phí vượt doanh thu | trung bình | lọc SQL trước, model rẻ, đo liên tục |

## 6. Giả định cần kiểm chứng
- [ ] Nhân viên sẵn sàng duyệt 20-50 tin/ngày
- [ ] Dữ liệu khách hàng có đủ trường cần thiết
- [ ] Khách không khó chịu khi nhận tin nhắn nhắc

## 7. Vì sao cần AI (và phần nào KHÔNG cần)
| Chức năng | AI hay không | Lý do |
|---|---|---|
| Phát hiện cơ hội | KHÔNG — SQL | luật rõ, cần chính xác tuyệt đối |
| Ước tính giá trị | KHÔNG — code | công thức cố định |
| Giải thích | CÓ | cần diễn đạt tự nhiên |
| Soạn tin nhắn | CÓ | sinh ngôn ngữ |
| Quyết định gửi | KHÔNG — người | rủi ro thương hiệu |
```

Mục 7 là mục quan trọng nhất — nó chứng minh bạn hiểu Ngày 1 và Ngày 60.

---

## 2. PASS/FAIL

- [ ] Có **trích dẫn từ người thật** (hoặc ≥ 5 nguồn công khai) về vấn đề
- [ ] PRD ≤ 2 trang, không lan man
- [ ] Phạm vi "KHÔNG CÓ" có ≥ 5 mục
- [ ] Chỉ số thành công có con số cụ thể, đo được
- [ ] Mục 7 chỉ rõ phần nào **không** dùng AI
- [ ] Giả định cần kiểm chứng được liệt kê, không giấu

---

## 3. Quiz + commit

```powershell
python quiz\quiz.py --day 76 ; python quiz\quiz.py --review
git add . ; git commit -m "day 76: CareDesk-AI PRD"
```
