# NGÀY 41 — Chunking strategies

> Phase 3 · 25' lý thuyết — 10' tài liệu — 75' code — 10' note
> ⭐ Đây là ngày có **tác động lớn nhất** đến chất lượng RAG của bạn.

## 🎯 Mục tiêu

Cài 4 chiến lược chunk, đo trên bộ test Ngày 35, chọn ra chiến lược thắng bằng **số liệu**.

---

## 1. Lý thuyết cốt lõi (25 phút)

### 1.1 Đánh đổi cốt lõi

```
Chunk NHỎ (200 token)          Chunk LỚN (1500 token)
├ embedding tập trung, chính xác  ├ embedding bị pha loãng
├ ít nhiễu trong context          ├ nhiều nhiễu
└ ✗ THIẾU NGỮ CẢNH               └ ✓ đủ ngữ cảnh để trả lời
```

Điểm cân bằng phổ biến: **400–800 token**, nhưng **phải đo trên dữ liệu của bạn**.

### 1.2 Bốn chiến lược

| Chiến lược | Cách cắt | Ưu | Nhược |
|---|---|---|---|
| **Fixed-size** | N ký tự/token, có overlap | đơn giản, đoán được | cắt giữa câu, giữa ý |
| **Recursive** | thử tách theo `\n\n` → `\n` → `. ` → khoảng trắng | tôn trọng ranh giới tự nhiên | vẫn có thể cắt giữa mục |
| **Structure-aware** ⭐ | cắt theo heading/section (Ngày 39) | ranh giới ngữ nghĩa đúng | cần tài liệu có cấu trúc |
| **Semantic** | cắt khi embedding của câu kế tiếp lệch nhiều | chất lượng tốt nhất trên lý thuyết | tốn tiền embed, chậm, khó đoán |

### 1.3 Overlap — vì sao cần

```
Chunk 1: "...khách được hoàn 80% giá trị buổi chưa dùng,"
Chunk 2: "trừ phí xử lý 200.000đ."
```
Không overlap → mất liên kết. Overlap 10–20% giữ được câu vắt ngang.

Đánh đổi: overlap 20% = tăng 20% chi phí lưu trữ và embedding.

### 1.4 Ba kỹ thuật làm giàu chunk (rẻ, hiệu quả cao)

```
1. THÊM SECTION PATH   : "Chính sách > 3.2 Hoàn tiền\n\n{nội dung}"
2. THÊM CÂU TÓM TẮT    : 1 câu mô tả chunk, sinh 1 lần khi ingest
3. THÊM CÂU HỎI GIẢ ĐỊNH: "Câu hỏi có thể trả lời: ..." (HyDE ngược)
```

Kỹ thuật 1 gần như **miễn phí** và thường cải thiện recall rõ rệt. Làm ngay.

### 1.5 Small-to-big retrieval

Tìm bằng chunk **nhỏ** (chính xác), nhưng đưa cho LLM chunk **lớn** bao quanh (đủ ngữ cảnh). Cách làm: lưu `parent_id` trong metadata, sau khi tìm được thì lấy parent.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Pinecone — Chunking strategies | https://www.pinecone.io/learn/chunking-strategies/ |
| LangChain text splitters (tham khảo ý tưởng) | https://python.langchain.com/docs/concepts/text_splitters/ |

---

## 3. Thực hành (75 phút)

`leanai_core/chunking.py`:

```python
"""Bốn chiến lược chunking + làm giàu chunk."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")


def ntok(t: str) -> int:
    return len(ENC.encode(t))


@dataclass
class TextChunk:
    text: str
    index: int
    meta: dict = field(default_factory=dict)
    parent_text: str = ""

    @property
    def tokens(self) -> int:
        return ntok(self.text)


# ---------- 1. Fixed size ----------
def chunk_fixed(text: str, size: int = 600, overlap: int = 100) -> list[TextChunk]:
    ids = ENC.encode(text)
    out, i, idx = [], 0, 0
    step = max(size - overlap, 1)
    while i < len(ids):
        piece = ENC.decode(ids[i:i + size])
        out.append(TextChunk(text=piece, index=idx))
        i += step; idx += 1
    return out


# ---------- 2. Recursive ----------
def chunk_recursive(text: str, size: int = 600, overlap: int = 100,
                    seps: tuple = ("\n\n", "\n", ". ", " ")) -> list[TextChunk]:
    def split(t: str, level: int = 0) -> list[str]:
        if ntok(t) <= size:
            return [t]
        if level >= len(seps):
            return [ENC.decode(ENC.encode(t)[:size])]
        parts, buf, out = t.split(seps[level]), "", []
        for p in parts:
            cand = (buf + seps[level] + p) if buf else p
            if ntok(cand) <= size:
                buf = cand
            else:
                if buf:
                    out.append(buf)
                out.extend(split(p, level + 1) if ntok(p) > size else [p])
                buf = ""
        if buf:
            out.append(buf)
        return out

    pieces = [p.strip() for p in split(text) if p.strip()]
    # thêm overlap bằng cách nối đuôi chunk trước
    out = []
    for i, p in enumerate(pieces):
        if i > 0 and overlap:
            tail = ENC.decode(ENC.encode(pieces[i - 1])[-overlap:])
            p = tail + " " + p
        out.append(TextChunk(text=p, index=i))
    return out


# ---------- 3. Structure-aware ----------
def chunk_by_section(sections: dict[str, str], max_tokens: int = 800,
                     min_tokens: int = 80) -> list[TextChunk]:
    """sections: {section_path: nội dung} từ parse_docx().sections()"""
    out, idx = [], 0
    for path, content in sections.items():
        content = content.strip()
        if not content:
            continue
        full = f"{path}\n\n{content}"              # làm giàu bằng section path
        if ntok(full) <= max_tokens:
            if ntok(content) >= min_tokens or not out:
                out.append(TextChunk(text=full, index=idx,
                                     meta={"section": path})); idx += 1
            else:                                   # chunk quá nhỏ -> gộp vào trước
                out[-1].text += "\n\n" + full
        else:
            for sub in chunk_recursive(content, size=max_tokens - ntok(path) - 4):
                out.append(TextChunk(text=f"{path}\n\n{sub.text}", index=idx,
                                     meta={"section": path},
                                     parent_text=full))       # small-to-big
                idx += 1
    return out


# ---------- 4. Semantic ----------
def chunk_semantic(text: str, embedder, threshold: float = 0.55,
                   max_tokens: int = 800) -> list[TextChunk]:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sents) < 2:
        return [TextChunk(text=text, index=0)]
    vecs = embedder.embed(sents)
    out, buf, idx = [], [sents[0]], 0
    for i in range(1, len(sents)):
        sim = float(vecs[i] @ vecs[i - 1])
        cand = " ".join(buf + [sents[i]])
        if sim < threshold or ntok(cand) > max_tokens:
            out.append(TextChunk(text=" ".join(buf), index=idx)); idx += 1
            buf = [sents[i]]
        else:
            buf.append(sents[i])
    if buf:
        out.append(TextChunk(text=" ".join(buf), index=idx))
    return out


def stats(chunks: list[TextChunk]) -> dict:
    t = [c.tokens for c in chunks]
    return {"số chunk": len(chunks), "token TB": round(float(np.mean(t)), 1),
            "min": min(t), "max": max(t),
            "quá nhỏ (<50)": sum(1 for x in t if x < 50),
            "quá lớn (>1000)": sum(1 for x in t if x > 1000)}
```

`exercises/day41/chunk_compare.py`:

```python
"""Ngày 41: so sánh 4 chiến lược chunk trên bộ test thật."""
from leanai_core.chunking import (chunk_fixed, chunk_recursive,
                                  chunk_by_section, chunk_semantic, stats)
from leanai_core.embedding import EmbeddingService
from leanai_core.parsers.word import parse_docx
from leanai_core.vectorstore import VectorStore, Chunk
from leanai_core.retrieval_eval import load_cases, evaluate, print_report

emb = EmbeddingService()
doc = parse_docx("data/docs/chinh-sach.docx")
text = doc.full_text
cases = load_cases("templates/retrieval-testset.json")

STRATEGIES = {
 "fixed-600":      lambda: chunk_fixed(text, 600, 100),
 "recursive-600":  lambda: chunk_recursive(text, 600, 100),
 "section-aware":  lambda: chunk_by_section(doc.sections(), 800),
 "semantic":       lambda: chunk_semantic(text, emb),
}

summary = {}
for name, fn in STRATEGIES.items():
    chunks = fn()
    print(f"\n=== {name} === {stats(chunks)}")

    vs = VectorStore(f"chunk_{name.replace('-','_')}", embedder=emb)
    vs.upsert([Chunk(text=c.text,
                     meta={"tenant_id": "clinic_001", "doc_id": "chinh-sach.docx",
                           "chunk_index": c.index, **c.meta})
               for c in chunks])

    def search(q, k, _vs=vs):
        return [f"chinh-sach.docx#chunk{h.meta['chunk_index']}"
                for h in _vs.search(q, k=k, where={"tenant_id": "clinic_001"})]

    r = evaluate(search, cases)
    print_report(name, r)
    summary[name] = r

print("\n=== BẢNG TỔNG HỢP ===")
print(f"{'chiến lược':<16} {'recall@5':>9} {'MRR':>7} {'#chunk':>8} {'token TB':>9}")
for name, r in summary.items():
    c = STRATEGIES[name]()
    print(f"{name:<16} {r['recall@5']:>9.3f} {r['mrr']:>7.3f} "
          f"{len(c):>8} {stats(c)['token TB']:>9}")
```

---

## 4. Bài tập

**Bài 1 — Quét kích thước.** Với chiến lược thắng, thử size = 300, 500, 800, 1200 và overlap = 0, 10%, 20%. Lập bảng recall@5. Tìm cấu hình tốt nhất. **Ghi vào `progress/notes/day41-chunking.md` — đây là cấu hình bạn dùng cho cả Phase 3 và Phase 6.**

**Bài 2 — Section path có đáng không.** Với `chunk_by_section`, chạy 2 lần: có và không thêm section path vào text. So sánh recall. Mức cải thiện bao nhiêu?

**Bài 3 — Small-to-big.** Cài retrieval: tìm bằng chunk nhỏ (300 token), trả cho LLM `parent_text` (800 token). So sánh chất lượng **câu trả lời cuối** (không chỉ recall) trên 10 câu hỏi.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 41 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Cài được cả 4 chiến lược
- [ ] Có bảng so sánh recall@5 trên **cùng** bộ test
- [ ] Xác định được cấu hình chunk tốt nhất + ghi lại lý do
- [ ] Chứng minh được tác dụng của section path bằng số
- [ ] Không còn chunk < 50 token hoặc > 1000 token
- [ ] Quiz ≥ 80%
