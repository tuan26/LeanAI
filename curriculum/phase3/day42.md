# NGÀY 42 — Metadata design (chốt schema)

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Chốt schema metadata cuối cùng cho cả dự án, và cài **lớp làm giàu metadata tự động** khi ingest.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Metadata đến từ đâu

```
1. TỪ HỆ THỐNG (miễn phí, chính xác 100%)
   tenant_id, doc_id, ingested_at, file size, mime type, chunk_index, hash

2. TỪ PARSER (miễn phí, chính xác cao)
   page, section_path, heading level, table/paragraph, token_count

3. TỪ QUY TẮC (rẻ, chính xác vừa)
   doc_type suy từ tên file/thư mục, branch suy từ đường dẫn, language detect

4. TỪ LLM (tốn tiền, dùng có chọn lọc)
   tóm tắt 1 câu, từ khoá, câu hỏi giả định, phân loại chủ đề
```

> **Ưu tiên tầng 1–3.** Chỉ dùng LLM (tầng 4) khi đo được nó cải thiện recall — và chỉ chạy **một lần lúc ingest**, không phải mỗi lần truy vấn.

### 1.2 Ba câu hỏi để quyết định một trường metadata

```
1. Tôi sẽ LỌC theo trường này không?     → nếu có: cần payload index
2. Tôi cần nó để TRÍCH DẪN không?        → nếu có: phải lưu trong payload
3. Nó có thay đổi theo thời gian không?  → nếu có: cần chiến lược cập nhật
```

Trường không trả lời "có" cho câu nào → **đừng lưu**. Metadata thừa làm chậm và tốn chỗ.

### 1.3 Versioning — vấn đề hay bị bỏ qua

Bảng giá 2025 và 2026 cùng tồn tại trong hệ thống. Nếu không có `effective_from/to` + `status`, AI sẽ trả lời giá cũ. Đây là lỗi **trực tiếp gây thiệt hại tiền** cho khách hàng.

Ba cách xử lý:
| Cách | Mô tả |
|---|---|
| Hard delete | xoá bản cũ — mất lịch sử, không audit được |
| **Soft delete** ⭐ | `status = archived`, filter mặc định loại ra |
| Time travel | lưu tất cả, filter theo ngày truy vấn |

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Qdrant — Payload | https://qdrant.tech/documentation/concepts/payload/ |
| Anthropic — Contextual retrieval | https://www.anthropic.com/news/contextual-retrieval |

---

## 3. Thực hành (80 phút)

`leanai_core/enrich.py`:

```python
"""Làm giàu metadata khi ingest."""
from __future__ import annotations

import re
from pathlib import Path

from .llm import LLMClient
from .metadata import ChunkMeta, DocType

DOC_TYPE_RULES = [
    (r"chinh[-_ ]?sach|policy|quy[-_ ]?dinh", DocType.POLICY),
    (r"bang[-_ ]?gia|price|gia[-_ ]?dich[-_ ]?vu", DocType.PRICE),
    (r"quy[-_ ]?trinh|procedure|sop|huong[-_ ]?dan", DocType.PROCEDURE),
    (r"faq|cau[-_ ]?hoi|hoi[-_ ]?dap", DocType.FAQ),
    (r"hop[-_ ]?dong|contract|thoa[-_ ]?thuan", DocType.CONTRACT),
]


def infer_doc_type(path: str | Path) -> DocType:
    s = str(path).lower()
    for pattern, t in DOC_TYPE_RULES:
        if re.search(pattern, s):
            return t
    return DocType.OTHER


def infer_branch(path: str | Path) -> str:
    m = re.search(r"(q\d{1,2}|quan[-_ ]?\d{1,2}|chi[-_ ]?nhanh[-_ ]?([a-z0-9]+))",
                  str(path).lower())
    return m.group(0).replace("quan", "q").replace("-", "").replace("_", "") if m else ""


CONTEXT_PROMPT = """<document_summary>
{doc_summary}
</document_summary>

<chunk>
{chunk}
</chunk>

Viết ĐÚNG 1 câu (tối đa 25 từ) đặt đoạn trên vào ngữ cảnh của tài liệu, để khi đọc
riêng đoạn này người ta vẫn hiểu nó nói về cái gì. Chỉ trả về câu đó, không giải thích."""


def contextualize(llm: LLMClient, chunk_text: str, doc_summary: str) -> str:
    """Contextual retrieval: thêm 1 câu ngữ cảnh vào đầu chunk. Chạy 1 lần lúc ingest."""
    r = llm.complete(CONTEXT_PROMPT.format(doc_summary=doc_summary[:1500],
                                           chunk=chunk_text[:2000]),
                     temperature=0, max_tokens=80, tag="enrich-context")
    return r.text.strip()


def summarize_doc(llm: LLMClient, full_text: str) -> str:
    r = llm.complete(
        f"<document>\n{full_text[:8000]}\n</document>\n\n"
        "Tóm tắt tài liệu trên trong 3 câu: nó là loại tài liệu gì, nói về chủ đề gì, "
        "áp dụng cho ai/khi nào. Chỉ trả về tóm tắt.",
        temperature=0, max_tokens=200, tag="enrich-summary")
    return r.text.strip()


def build_meta(*, tenant_id: str, path: str | Path, chunk_index: int, text: str,
               page: int | None = None, section: str = "",
               title: str = "", **extra) -> ChunkMeta:
    p = Path(path)
    return ChunkMeta(
        tenant_id=tenant_id, doc_id=p.name, chunk_index=chunk_index,
        chunk_hash=ChunkMeta.hash_text(text),
        title=title or p.stem, page=page, section=section,
        source_uri=str(p.resolve()),
        doc_type=infer_doc_type(p), branch=infer_branch(p),
        token_count=len(text) // 3, **extra)
```

`exercises/day42/enrich_eval.py`:

```python
"""Ngày 42: contextual retrieval có đáng tiền không?"""
from leanai_core.llm import LLMClient
from leanai_core.embedding import EmbeddingService
from leanai_core.vectorstore import VectorStore, Chunk
from leanai_core.chunking import chunk_by_section
from leanai_core.parsers.word import parse_docx
from leanai_core.enrich import summarize_doc, contextualize
from leanai_core.retrieval_eval import load_cases, evaluate, print_report

llm, emb = LLMClient(), EmbeddingService()
doc = parse_docx("data/docs/chinh-sach.docx")
chunks = chunk_by_section(doc.sections(), 800)
cases = load_cases("templates/retrieval-testset.json")

summary = summarize_doc(llm, doc.full_text)
print(f"Tóm tắt tài liệu: {summary}\n")

VARIANTS = {"plain": None, "contextual": summary}
for name, doc_sum in VARIANTS.items():
    vs = VectorStore(f"enrich_{name}", embedder=emb)
    items = []
    for c in chunks:
        text = c.text
        if doc_sum:
            text = contextualize(llm, c.text, doc_sum) + "\n\n" + c.text
        items.append(Chunk(text=text, meta={"tenant_id": "clinic_001",
                                            "doc_id": "chinh-sach.docx",
                                            "chunk_index": c.index}))
    vs.upsert(items)

    def search(q, k, _vs=vs):
        return [f"chinh-sach.docx#chunk{h.meta['chunk_index']}"
                for h in _vs.search(q, k=k, where={"tenant_id": "clinic_001"})]
    print_report(name, evaluate(search, cases))

print("\n" + llm.usage.report())
print("Câu hỏi: mức cải thiện recall có xứng với chi phí enrich 1 lần không?")
```

---

## 4. Bài tập

**Bài 1 — Chốt schema.** Hoàn thiện `templates/schemas/chunk-metadata.md`: bảng đầy đủ mọi trường với cột `nguồn (tầng 1-4) | kiểu | bắt buộc | có index | dùng để lọc gì`. Đây là tài liệu kỹ thuật chính thức của dự án.

**Bài 2 — Đo contextual retrieval.** Chạy `enrich_eval.py`. Ghi: mức tăng recall@5, chi phí enrich cho 100 chunk, thời gian ingest tăng bao nhiêu. Kết luận dùng hay không.

**Bài 3 — Versioning.** Nạp bảng giá 2025 (`status=archived`) và 2026 (`approved`). Viết hàm `search_current()` luôn filter `status=approved` và `effective_from <= hôm nay`. Chứng minh bằng test: hỏi giá → **không bao giờ** trả về giá 2025.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 42 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Schema metadata được chốt và tài liệu hoá đầy đủ
- [ ] Suy luận tự động được doc_type và branch từ đường dẫn
- [ ] Có số liệu đánh giá contextual retrieval (tăng recall vs chi phí)
- [ ] Versioning hoạt động: không bao giờ trả về tài liệu archived
- [ ] Quiz ≥ 80%
