# ROADMAP 90 NGÀY

Ký hiệu: 📄 note/tài liệu · 💻 code chạy được · 📊 số liệu đo được · 🚀 sản phẩm

## PHASE 1 — AI FUNDAMENTALS (Ngày 1–14)
Mục tiêu: hiểu LLM đủ sâu để không dùng AI kiểu black box.

| Ngày | Nội dung | Output |
|---|---|---|
| [1](curriculum/phase1/day01.md) | AI vs ML vs DL vs LLM | 📄 1 trang note phân biệt 4 khái niệm |
| [2](curriculum/phase1/day02.md) | Neural Network | 💻 neuron + forward pass bằng numpy |
| [3](curriculum/phase1/day03.md) | Transformer | 📄 sơ đồ Transformer tự vẽ |
| [4](curriculum/phase1/day04.md) | Tokenization | 💻 tokenizer demo + đếm token tiếng Việt |
| [5](curriculum/phase1/day05.md) | Embedding | 💻 semantic similarity demo |
| [6](curriculum/phase1/day06.md) | Attention | 💻 self-attention 20 dòng numpy |
| [7](curriculum/phase1/day07.md) | Ôn tập tuần 1 | 📄 bài viết "LLM hoạt động thế nào?" |
| [8](curriculum/phase1/day08.md) | Context window | 📊 đo giới hạn context thực tế |
| [9](curriculum/phase1/day09.md) | Temperature / sampling | 📊 bảng so sánh output theo temperature |
| [10](curriculum/phase1/day10.md) | Pretraining | 📄 note vòng đời model |
| [11](curriculum/phase1/day11.md) | Instruction tuning | 📄 so sánh base vs instruct |
| [12](curriculum/phase1/day12.md) | RLHF / preference optimization | 📄 note + ví dụ reward hacking |
| [13](curriculum/phase1/day13.md) | Hallucination | 📊 đo tỉ lệ bịa trên 20 câu hỏi |
| [14](curriculum/phase1/day14.md) | Mini project: AI Explanation Engine | 🚀 CLI chạy được |

## PHASE 2 — LLM APPLICATION ENGINEERING (Ngày 15–30)
Mục tiêu: gọi LLM như một kỹ sư, không như người dùng ChatGPT.

| Ngày | Nội dung | Output |
|---|---|---|
| [15](curriculum/phase2/day15.md) | Python env, API, JSON | 💻 script gọi HTTP API bất kỳ |
| [16](curriculum/phase2/day16.md) | LLM API request đầu tiên | 💻 `llm_client.py` |
| [17](curriculum/phase2/day17.md) | system / user / assistant messages | 💻 so sánh 3 kiểu system prompt |
| [18](curriculum/phase2/day18.md) | Conversation & memory | 💻 chatbot nhớ ngữ cảnh |
| [19](curriculum/phase2/day19.md) | Streaming | 💻 stream + đo TTFT |
| [20](curriculum/phase2/day20.md) | Error handling & retry | 💻 client chịu lỗi 429/500 |
| [21](curriculum/phase2/day21.md) | Mini chatbot | 🚀 CLI chatbot hoàn chỉnh |
| [22](curriculum/phase2/day22.md) | Zero-shot prompting | 📊 20 prompt + kết quả |
| [23](curriculum/phase2/day23.md) | Few-shot prompting | 📊 đo cải thiện vs zero-shot |
| [24](curriculum/phase2/day24.md) | Role & context | 📄 thư viện system prompt |
| [25](curriculum/phase2/day25.md) | Constraints & format control | 💻 prompt ép định dạng |
| [26](curriculum/phase2/day26.md) | Decomposition (chain/plan) | 💻 pipeline nhiều bước |
| [27](curriculum/phase2/day27.md) | Self-verification | 💻 critic pass |
| [28](curriculum/phase2/day28.md) | Prompt injection | 📊 10 payload tấn công + phòng thủ |
| [29](curriculum/phase2/day29.md) | JSON output | 💻 output JSON 100% parse được |
| [30](curriculum/phase2/day30.md) | Schema validation + **Project #1** | 🚀 AI Business Analyst |

## PHASE 3 — RAG (Ngày 31–50)
Mục tiêu: RAG production, không phải RAG tutorial.

| Ngày | Nội dung | Output |
|---|---|---|
| [31](curriculum/phase3/day31.md) | Embedding thực chiến | 💻 embed + cache |
| [32](curriculum/phase3/day32.md) | Cosine similarity | 💻 tự cài similarity, so với thư viện |
| [33](curriculum/phase3/day33.md) | Vector database (Qdrant) | 💻 collection chạy Docker |
| [34](curriculum/phase3/day34.md) | Metadata & filtering | 💻 filter theo tenant/doc/date |
| [35](curriculum/phase3/day35.md) | Semantic search | 📊 recall@5 trên 20 truy vấn |
| [36](curriculum/phase3/day36.md) | Hybrid search (BM25 + vector) | 📊 so sánh 3 chiến lược |
| [37](curriculum/phase3/day37.md) | Mini RAG end-to-end | 🚀 hỏi–đáp trên 10 tài liệu |
| [38](curriculum/phase3/day38.md) | PDF parsing | 💻 parser + xử lý PDF scan |
| [39](curriculum/phase3/day39.md) | Word parsing | 💻 giữ heading làm metadata |
| [40](curriculum/phase3/day40.md) | Excel parsing | 💻 bảng → text có ngữ nghĩa |
| [41](curriculum/phase3/day41.md) | Chunking strategies | 📊 so sánh 4 cách chunk |
| [42](curriculum/phase3/day42.md) | Metadata design | 📄 schema metadata chuẩn |
| [43](curriculum/phase3/day43.md) | Indexing & incremental update | 💻 re-index không trùng |
| [44](curriculum/phase3/day44.md) | Ingestion pipeline | 🚀 1 lệnh ingest cả thư mục |
| [45](curriculum/phase3/day45.md) | Query rewriting | 📊 đo cải thiện recall |
| [46](curriculum/phase3/day46.md) | Top-k & context budget | 📊 bảng k vs accuracy vs cost |
| [47](curriculum/phase3/day47.md) | Reranking | 📊 nDCG trước/sau rerank |
| [48](curriculum/phase3/day48.md) | Citation | 💻 mọi câu trả lời có nguồn |
| [49](curriculum/phase3/day49.md) | Hallucination control | 📊 tỉ lệ bịa < 5% |
| [50](curriculum/phase3/day50.md) | RAG evaluation + **Project #2** | 🚀 Company Knowledge AI + 100 câu test |

## PHASE 4 — AI AGENT (Ngày 51–65)
Mục tiêu: chuyển từ "AI trả lời" sang "AI làm việc".

| Ngày | Nội dung | Output |
|---|---|---|
| [51](curriculum/phase4/day51.md) | Function calling | 💻 1 tool chạy được |
| [52](curriculum/phase4/day52.md) | Tool calling nhiều tool | 💻 LLM tự chọn tool |
| [53](curriculum/phase4/day53.md) | Tool schema design | 📄 quy tắc viết schema |
| [54](curriculum/phase4/day54.md) | Tool result handling | 💻 feed kết quả về LLM |
| [55](curriculum/phase4/day55.md) | Tool error | 💻 lỗi tool không làm chết agent |
| [56](curriculum/phase4/day56.md) | Retry & backoff | 💻 retry có giới hạn |
| [57](curriculum/phase4/day57.md) | Agent loop | 💻 vòng lặp agent tự viết |
| [58](curriculum/phase4/day58.md) | State | 💻 state machine của agent |
| [59](curriculum/phase4/day59.md) | Memory (short/long) | 💻 tóm tắt + truy hồi |
| [60](curriculum/phase4/day60.md) | Workflow vs agent | 📄 quyết định khi nào dùng cái nào |
| [61](curriculum/phase4/day61.md) | Human-in-the-loop | 💻 approve / edit / reject |
| [62](curriculum/phase4/day62.md) | Guardrails | 💻 chặn hành động nguy hiểm |
| [63](curriculum/phase4/day63.md) | Multi-step agent | 💻 agent 5+ bước ổn định |
| [64](curriculum/phase4/day64.md) | Logging & observability | 💻 log đủ để debug |
| [65](curriculum/phase4/day65.md) | **Project #3** | 🚀 Research Agent (30 nhà cung cấp) |

## PHASE 5 — AI ENGINEERING (Ngày 66–75)
Mục tiêu: phần mà đa số người bỏ qua — và là lý do sản phẩm của họ chết.

| Ngày | Nội dung | Output |
|---|---|---|
| [66](curriculum/phase5/day66.md) | Evaluation: dataset | 📊 50 case có expected answer |
| [67](curriculum/phase5/day67.md) | Evaluation: scorer & LLM-judge | 💻 auto-score + đo agreement |
| [68](curriculum/phase5/day68.md) | Tracing: span model | 💻 trace 1 request đủ 6 tầng |
| [69](curriculum/phase5/day69.md) | Tracing: viewer & debug | 💻 xem lại trace, tìm bottleneck |
| [70](curriculum/phase5/day70.md) | Cost optimization | 📊 cost/request, /user, /month |
| [71](curriculum/phase5/day71.md) | Latency | 📊 TTFT, p50/p95 từng tầng |
| [72](curriculum/phase5/day72.md) | Security | 📊 báo cáo 5 lỗ hổng + fix |
| [73](curriculum/phase5/day73.md) | Guardrails in/out | 💻 reject / rewrite / escalate |
| [74](curriculum/phase5/day74.md) | Reliability | 💻 timeout, fallback, idempotency |
| [75](curriculum/phase5/day75.md) | Production AI checklist | 📄 checklist riêng của bạn |

## PHASE 6 — AI SaaS: CAPSTONE CareDesk-AI (Ngày 76–90)

| Ngày | Nội dung | Output |
|---|---|---|
| [76](curriculum/phase6/day76.md) | Domain & problem framing | 📄 PRD 2 trang |
| [77](curriculum/phase6/day77.md) | Architecture | 📄 sơ đồ + ADR |
| [78](curriculum/phase6/day78.md) | Data model | 💻 schema + migration |
| [79](curriculum/phase6/day79.md) | Auth | 💻 login/session |
| [80](curriculum/phase6/day80.md) | Multi-tenant isolation | 📊 test chứng minh A không thấy B |
| [81](curriculum/phase6/day81.md) | Tenant-scoped RAG | 💻 KB riêng từng clinic |
| [82](curriculum/phase6/day82.md) | Revenue Opportunity engine (rule) | 💻 5 loại cơ hội |
| [83](curriculum/phase6/day83.md) | Opportunity scoring | 💻 value + confidence |
| [84](curriculum/phase6/day84.md) | Explanation layer | 💻 "vì sao" có dẫn chứng |
| [85](curriculum/phase6/day85.md) | Agent: detect → recommend | 💻 agent chạy trên data thật |
| [86](curriculum/phase6/day86.md) | Agent: draft message | 💻 tin nhắn Zalo/SMS đúng tone |
| [87](curriculum/phase6/day87.md) | Human approval + send | 💻 Approve/Edit/Reject + gửi |
| [88](curriculum/phase6/day88.md) | Dashboard | 🚀 5 chỉ số quan trọng |
| [89](curriculum/phase6/day89.md) | Evaluation 100 scenarios | 📊 precision/recall/cost/latency |
| [90](curriculum/phase6/day90.md) | Demo Day | 🚀 demo 8 phút + số liệu |
