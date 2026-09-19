# Tài liệu — đã lọc, không lan man

> Nguyên tắc: mỗi mục ở đây đều được dùng ở một ngày cụ thể. Không có mục nào "để đọc thêm cho biết".

## 📺 Video nền tảng (xem theo thứ tự)

| Nguồn | Link | Dùng ở ngày |
|---|---|---|
| 3Blue1Brown — But what is a neural network? | https://www.youtube.com/watch?v=aircAruvnKk | 1, 2 |
| 3Blue1Brown — Gradient descent | https://www.youtube.com/watch?v=IHZwWFHWa-w | 2 |
| 3Blue1Brown — But what is a GPT? | https://www.youtube.com/watch?v=wjZofJX0v4M | 3 |
| 3Blue1Brown — Attention in transformers | https://www.youtube.com/watch?v=eMlx5fFNoYc | 6 |
| Karpathy — Let's build the GPT Tokenizer | https://www.youtube.com/watch?v=zduSFxRajkE | 4 |
| Karpathy — Intro to LLMs | https://www.youtube.com/watch?v=zjkBMFhNj_g | 10 |
| Karpathy — Let's build GPT from scratch | https://www.youtube.com/watch?v=kCc8FmEb1nY | 6 (tuỳ chọn) |

## 📖 Bài viết phải đọc

| Nguồn | Link | Ngày |
|---|---|---|
| Jay Alammar — Illustrated Transformer | https://jalammar.github.io/illustrated-transformer/ | 3, 6 |
| Jay Alammar — Illustrated Word2vec | https://jalammar.github.io/illustrated-word2vec/ | 5 |
| Anthropic — Building effective agents | https://www.anthropic.com/research/building-effective-agents | 57, 60, 61 |
| Anthropic — Contextual retrieval | https://www.anthropic.com/news/contextual-retrieval | 42 |
| Pinecone — Chunking strategies | https://www.pinecone.io/learn/chunking-strategies/ | 41 |
| Hamel Husain — Your AI product needs evals | https://hamel.dev/blog/posts/evals/ | 66 |
| Simon Willison — Prompt injection series | https://simonwillison.net/series/prompt-injection/ | 28 |
| AWS — Timeouts, retries, backoff with jitter | https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/ | 20, 56 |
| Google SRE — Handling overload | https://sre.google/sre-book/handling-overload/ | 74 |

## 📄 Paper (chỉ đọc abstract + hình chính)

| Paper | Link | Ngày |
|---|---|---|
| Attention Is All You Need | https://arxiv.org/abs/1706.03762 | 3 |
| Lost in the Middle | https://arxiv.org/abs/2307.03172 | 8, 46 |
| InstructGPT | https://arxiv.org/abs/2203.02155 | 11 |
| DPO | https://arxiv.org/abs/2305.18290 | 12 |
| LoRA | https://arxiv.org/abs/2106.09685 | 11 |
| HyDE | https://arxiv.org/abs/2212.10496 | 45 |
| HNSW | https://arxiv.org/abs/1603.09320 | 32, 33 |
| ReAct | https://arxiv.org/abs/2210.03629 | 63 |
| Judging LLM-as-a-Judge | https://arxiv.org/abs/2306.05685 | 67 |
| Survey of Hallucination in LLMs | https://arxiv.org/abs/2311.05232 | 13 |

## 🛠 Tài liệu kỹ thuật (tra khi cần)

| Chủ đề | Link |
|---|---|
| Anthropic API — Messages | https://docs.anthropic.com/en/api/messages |
| Anthropic — Tool use | https://docs.anthropic.com/en/docs/build-with-claude/tool-use |
| Anthropic — Prompt engineering | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering |
| Anthropic — Prompt caching | https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching |
| Anthropic — Citations | https://docs.anthropic.com/en/docs/build-with-claude/citations |
| Anthropic — Streaming | https://docs.anthropic.com/en/api/messages-streaming |
| Anthropic — Reduce hallucinations | https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-hallucinations |
| OpenAI — Embeddings guide | https://platform.openai.com/docs/guides/embeddings |
| OpenAI — Tokenizer (chơi thử) | https://platform.openai.com/tokenizer |
| Qdrant — Documentation | https://qdrant.tech/documentation/ |
| Qdrant — Filtering | https://qdrant.tech/documentation/concepts/filtering/ |
| Postgres — Row Level Security | https://www.postgresql.org/docs/current/ddl-rowsecurity.html |
| FastAPI | https://fastapi.tiangolo.com/ |
| Pydantic v2 | https://docs.pydantic.dev/latest/ |
| OpenTelemetry — Traces | https://opentelemetry.io/docs/concepts/signals/traces/ |
| OWASP Top 10 for LLM | https://owasp.org/www-project-top-10-for-large-language-model-applications/ |

## 🐍 Thư viện dùng trong chương trình

| Thư viện | Dùng để | Ngày |
|---|---|---|
| `anthropic` | LLM API | 16+ |
| `tiktoken` | đếm token | 4+ |
| `pydantic` | schema validation | 30+ |
| `qdrant-client` | vector DB | 33+ |
| `rank-bm25` | keyword search | 36 |
| `pdfplumber`, `pypdf` | PDF | 38 |
| `python-docx` | Word | 39 |
| `openpyxl`, `pandas` | Excel | 40 |
| `fastapi`, `uvicorn` | API | 77+ |
| `sqlalchemy`, `alembic` | DB | 78+ |
| `pytest` | test | 72+ |

## ⚠️ Những thứ CỐ TÌNH không có trong danh sách

| Không học | Vì sao |
|---|---|
| LangChain / LlamaIndex | Bạn tự viết vòng lặp agent và pipeline RAG — hiểu bản chất trước, dùng framework sau nếu cần |
| Fine-tuning / LoRA thực hành | Không cần trong 90 ngày, xem Ngày 11 mục 1.3 |
| Training từ đầu, CUDA, distributed | Không tạo ra sản phẩm trong 90 ngày |
| PyTorch nâng cao | Chỉ cần numpy để hiểu nguyên lý (Ngày 2, 6) |
| Multi-agent phức tạp | Sau khi agent 1 con đã ổn định (Ngày 63) |

Sau ngày 90, nếu cần, quay lại theo thứ tự: LangGraph/framework → fine-tuning LoRA → multi-agent.

## 💰 Cập nhật giá

Giá API thay đổi theo thời gian. Mọi con số giá trong chương trình chỉ là tham khảo — **luôn kiểm tra bảng giá hiện hành** và cập nhật `leanai_core/config.py`:

```python
PRICE_IN = 3.00    # USD / 1 triệu token input
PRICE_OUT = 15.00  # USD / 1 triệu token output
```

https://www.anthropic.com/pricing
