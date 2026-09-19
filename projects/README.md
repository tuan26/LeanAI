# Projects — 4 sản phẩm vào portfolio

| # | Dự án | Xong ở ngày | Kỹ năng chứng minh |
|---|---|---|---|
| 0 | [AI Explanation Engine](p0-explanation-engine/) | 14 | Prompt có cấu trúc, chống bịa, verify trích dẫn |
| 0b | [CLI Chatbot](p0-chatbot/) | 21 | API, streaming, memory, retry, cost tracking |
| 1 | [AI Business Analyst](p1-ai-business-analyst/) | 30 | Pipeline nhiều bước, Pydantic validation, retry ngữ nghĩa |
| 2 | [Company Knowledge RAG](p2-company-knowledge-rag/) | 50 | RAG production, hybrid search, rerank, eval 100 câu |
| 3 | [Research Agent](p3-research-agent/) | 65 | Tool use, agent loop, khử trùng, báo cáo có nguồn |
| ★ | [CareDesk-AI](capstone-caredesk-ai/) | 90 | AI SaaS đầy đủ: multi-tenant, RBAC, guardrail, dashboard |

## Quy tắc chung cho mọi project

Mỗi project **bắt buộc** có 4 file:

```
README.md    — chạy lại được: yêu cầu, cài đặt, lệnh chạy, ví dụ output
EVAL.md      — số liệu đo được: bảng chỉ số, cấu hình so sánh, ca thất bại
LIMITS.md    — giới hạn đã biết, viết trung thực
<code>       — chạy được bằng một lệnh
```

> Project không có `EVAL.md` với số liệu thật thì **không tính là hoàn thành**. Đây là điểm khác biệt giữa "làm theo tutorial" và "kỹ sư AI".

## Cách dùng cho portfolio

Khi giới thiệu với nhà tuyển dụng hoặc khách hàng, mỗi project trình bày theo cấu trúc:

```
1. Bài toán   — ai đau ở đâu, đau bao nhiêu
2. Giải pháp  — kiến trúc, và phần nào KHÔNG dùng AI (kèm lý do)
3. Số liệu    — precision/recall, chi phí, latency
4. Giới hạn   — điều hệ thống chưa làm được
5. Bài học    — điều bạn làm khác nếu làm lại
```

Mục 4 và 5 là thứ khiến người nghe tin bạn. Đừng bỏ.
