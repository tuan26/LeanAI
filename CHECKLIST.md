# CHECKLIST 90 NGÀY

Tick khi **thật sự** làm được, không phải khi đã đọc qua.

---

## LLM — nền tảng (Phase 1)

- [ ] Giải thích AI / ML / DL / LLM trong 60 giây, không dùng thuật ngữ
- [ ] Biết khi nào **không** nên dùng LLM (3 câu hỏi sàng lọc)
- [ ] Viết được forward pass của một neuron trên giấy
- [ ] Vẽ được sơ đồ Transformer từ trí nhớ
- [ ] Giải thích được vai trò 8 khối của Transformer
- [ ] Đếm token và tính chi phí bất kỳ prompt nào
- [ ] Biết tỉ lệ token tiếng Việt / tiếng Anh (tự đo)
- [ ] Giải thích embedding + 2 giới hạn của nó bằng số liệu tự đo
- [ ] Viết được công thức attention và giải thích từng thành phần
- [ ] Giải thích được chi phí O(n²) và hệ quả
- [ ] Biết context window là gì và quy tắc sắp xếp prompt 4 tầng
- [ ] Chọn được temperature cho từng loại tác vụ (bảng tra)
- [ ] Phân biệt pretraining / instruction tuning / RLHF
- [ ] Biết 3 điều kiện được phép fine-tune
- [ ] Kể được 5 hành vi do RLHF gây ra và rủi ro sản phẩm
- [ ] Thuộc 6 kỹ thuật chống hallucination

## LLM Engineering (Phase 2)

- [ ] Gọi LLM API bằng HTTP thuần, hiểu SDK làm gì bên dưới
- [ ] Có `LLMClient` dùng chung: log, usage, cost, phát hiện output bị cắt
- [ ] Phân biệt system / user / assistant và biết dùng prefill
- [ ] Quản lý hội thoại có nén, facts tách khỏi lịch sử
- [ ] Stream và đo được TTFT / TPS
- [ ] Retry có backoff + jitter, không retry hành động ghi
- [ ] Có fallback và circuit breaker
- [ ] Viết prompt zero-shot đủ 6 thành phần với ràng buộc **đo được**
- [ ] Biết khi nào few-shot đáng dùng (có số liệu so sánh)
- [ ] Biết vai trò kiểu nào có tác dụng, kiểu nào chỉ tốn token
- [ ] Ép định dạng bằng 3 lớp: prompt + prefill + validate
- [ ] Chia nhiệm vụ thành pipeline, tách phần tính toán cho code
- [ ] Biết khi nào critic pass đáng tiền (đo cả false positive)
- [ ] Đã tự tấn công hệ thống bằng ≥ 10 payload injection
- [ ] JSON output parse được 100% (prefill + stop + parse mềm + retry)
- [ ] Dùng Pydantic validate, retry kèm lỗi cụ thể

## RAG (Phase 3)

- [ ] Có embedding service: cache + batch + chuẩn hoá
- [ ] Có bộ test tiếng Việt riêng để chọn model embedding
- [ ] Vector DB chạy được, có payload index cho trường lọc
- [ ] Schema metadata chốt, luôn có `tenant_id`
- [ ] Bộ test truy hồi ≥ 30 truy vấn có nhãn
- [ ] Đo được recall@k, precision@k, MRR, nDCG
- [ ] Hybrid search (BM25 + vector) gộp bằng RRF
- [ ] Parse được PDF / Word / Excel, có điểm chất lượng
- [ ] Phát hiện được PDF scan và injection ẩn trong tài liệu
- [ ] So sánh ≥ 4 chiến lược chunking bằng số liệu
- [ ] Index tăng dần: không trùng, không mồ côi, không embed lại phần không đổi
- [ ] Một lệnh ingest cả thư mục, không dừng khi gặp file lỗi
- [ ] Biết khi nào cần viết lại truy vấn (có router)
- [ ] Tìm được k tối ưu bằng thực nghiệm
- [ ] Rerank và biết nó có đáng dùng không (đo câu trả lời cuối)
- [ ] Citation mức 3: verify được tồn tại + nguyên văn + số liệu
- [ ] Tỉ lệ bịa < 5% **và** từ chối nhầm < 15%

## Agent (Phase 4)

- [ ] Hiểu LLM **không** tự chạy hàm
- [ ] Viết tool schema đúng 4 phần description
- [ ] Biết giới hạn số tool trước khi model chọn sai
- [ ] Nén được kết quả tool, hiểu chi phí O(N²)
- [ ] Lỗi tool không làm chết agent, có `hint` để agent tự sửa
- [ ] Chặn được vòng lặp lỗi (cùng tool + cùng tham số)
- [ ] Tự viết `Agent` class, không dùng framework
- [ ] Có đủ 5 điều kiện dừng
- [ ] State bền, khôi phục được sau khi kill process
- [ ] Phân biệt 4 loại bộ nhớ, không nhớ dữ liệu biến động
- [ ] Quyết định được workflow hay agent cho từng chức năng
- [ ] Human-in-the-loop: approve / edit / reject, reject bắt buộc có lý do
- [ ] Guardrail chạy bằng **code**, fail closed
- [ ] Đo độ tin cậy bằng cách chạy 10 lần/nhiệm vụ
- [ ] Log + trace đủ để điều tra sự cố 3 ngày trước

## AI Engineering (Phase 5)

- [ ] Bộ eval ≥ 50 case, nhãn do người gán, ≥ 25% ca âm
- [ ] Dev set và test set tách biệt, test set đóng băng
- [ ] LLM-judge đã hiệu chuẩn (đồng ý với người ≥ 85%)
- [ ] Trace ≥ 6 tầng, sampling giữ 100% ca lỗi/chậm
- [ ] Xác định nút thắt bằng số liệu, không bằng cảm tính
- [ ] Biết cost/request, cost/tenant/tháng
- [ ] Giảm được ≥ 40% chi phí mà không mất chất lượng
- [ ] Có bảng định giá với biên lợi nhuận
- [ ] Đo p50/p95/p99 từng tầng, có ngân sách latency
- [ ] Đã audit an ninh, tìm và vá ≥ 5 lỗ hổng
- [ ] Guardrail in/out: recall ≥ 95%, báo nhầm ≤ 3%
- [ ] Có đường đi dự phòng **không cần AI**
- [ ] Job dài có checkpoint, tỉ lệ gửi trùng = 0
- [ ] Có checklist production riêng + script preflight chặn deploy

## AI SaaS (Phase 6)

- [ ] PRD có trích dẫn từ người dùng thật
- [ ] 5 ADR với phương án bị loại và lý do
- [ ] Schema có `tenant_id` mọi bảng, tiền lưu số nguyên
- [ ] Auth: tenant_id chỉ từ session, phân quyền ở tầng service
- [ ] **RLS bật, test cách ly tenant pass 100%**
- [ ] RAG theo tenant, không rò rỉ trên 20 truy vấn
- [ ] Detector dùng rule, không dùng LLM
- [ ] Scoring xếp hạng theo giá trị kỳ vọng
- [ ] Giải thích không có số bịa, có fallback template
- [ ] Tin nhắn: LLM sinh biến, code thay số — 0 lỗi số liệu
- [ ] Approve/Edit/Reject + guardrail lần cuối + idempotency
- [ ] Dashboard 5 chỉ số, nổi bật doanh thu thu hồi
- [ ] Eval 100 kịch bản, precision ≥ 0.85
- [ ] Demo 8 phút chạy được, có số liệu, thừa nhận giới hạn

## Kinh doanh

- [ ] Nói được bài toán bằng số liệu thật, không phải giả định
- [ ] Biết ICP (khách hàng lý tưởng) của sản phẩm
- [ ] Tính được ROI cho khách hàng
- [ ] Có bảng định giá 3 gói với biên lợi nhuận
- [ ] Biết chi phí AI chiếm bao nhiêu % doanh thu
- [ ] Có chỉ số theo dõi: tỉ lệ duyệt thẳng, doanh thu thu hồi
- [ ] Nói được giới hạn sản phẩm với khách hàng mà vẫn bán được

---

## Tổng kết

```powershell
python quiz\quiz.py --exam 1 90      # cần ≥ 85%
python quiz\quiz.py --stats          # cần ≥ 80% câu ở box 5-6
git log --oneline | wc -l            # cần ≥ 90 commit
```

**Đã tick hết?** Bạn không còn là người "biết về AI".
