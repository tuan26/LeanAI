# NGÀY 68 — Tracing: mô hình span

> Phase 5 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Trace một request xuyên **6 tầng**: user → prompt → retrieval → LLM → tool → câu trả lời.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vì sao log dòng không đủ

Log dòng cho biết *cái gì đã xảy ra*. Trace cho biết *cái gì gây ra cái gì*, và *mất bao lâu ở đâu*.

```
request_id=r7 tổng 4.2s
├─ guardrail_check      0.01s
├─ query_rewrite        0.62s  ← có đáng không?
├─ retrieval            0.35s
│  ├─ embed_query       0.18s
│  ├─ vector_search     0.09s
│  └─ bm25_search       0.08s
├─ rerank               1.10s  ← chiếm 26% thời gian
├─ llm_answer           1.95s  ← in=3.2k out=180
└─ verify_citations     0.02s
```

Nhìn cây này bạn biết ngay phải tối ưu gì. Không có nó, bạn tối ưu theo cảm tính.

### 1.2 Thuộc tính bắt buộc của mỗi span

```
trace_id, span_id, parent_id, name, start, duration
+ tenant_id, user_id (để lọc)
+ với LLM span: model, input_tokens, output_tokens, cost, temperature
+ với retrieval span: k, số kết quả, điểm cao nhất
+ với tool span: tên tool, ok/lỗi
+ error nếu có
```

### 1.3 Sampling

Trace đầy đủ mọi request rất tốn dung lượng. Chiến lược thực tế:

```
- 100% request LỖI
- 100% request CHẬM (> p95)
- 100% request có hành động ghi (audit)
- 5-10% request bình thường
```

### 1.4 Liên kết trace với eval

Mỗi eval case chạy nên gắn `trace_id`. Khi một case thất bại, bạn mở đúng trace đó ra xem — đây là cách debug nhanh nhất có thể.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| OpenTelemetry — Traces | https://opentelemetry.io/docs/concepts/signals/traces/ |
| OpenTelemetry — GenAI semantic conventions | https://opentelemetry.io/docs/specs/semconv/gen-ai/ |

---

## 3. Thực hành (80 phút)

Mở rộng `leanai_core/logging.py` (Ngày 64) thành `leanai_core/tracing.py`:

```python
"""Tracing đầy đủ cho pipeline AI."""
from __future__ import annotations

import json
import random
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .logging import redact

TRACE_DIR = Path("logs/traces")
_ctx: ContextVar[dict] = ContextVar("trace_ctx", default={})


@dataclass
class SpanRecord:
    trace_id: str
    span_id: str
    parent_id: str
    name: str
    start_ms: float
    duration_ms: float = 0.0
    attrs: dict = field(default_factory=dict)
    error: str = ""


class Tracer:
    def __init__(self, sample_rate: float = 0.1):
        self.sample_rate = sample_rate
        self.spans: dict[str, list[SpanRecord]] = {}

    def start_trace(self, *, tenant_id: str = "", user_id: str = "",
                    force: bool = False) -> str:
        tid = str(uuid.uuid4())[:12]
        _ctx.set({"trace_id": tid, "stack": [], "tenant_id": tenant_id,
                  "user_id": user_id, "sampled": force or random.random() < self.sample_rate,
                  "force": force})
        self.spans[tid] = []
        return tid

    @contextmanager
    def span(self, name: str, **attrs):
        ctx = _ctx.get({})
        if not ctx:
            self.start_trace(force=False)
            ctx = _ctx.get({})
        sid = str(uuid.uuid4())[:8]
        parent = ctx["stack"][-1] if ctx["stack"] else ""
        ctx["stack"].append(sid)
        rec = SpanRecord(ctx["trace_id"], sid, parent, name,
                         time.time() * 1000, attrs=dict(attrs))
        t0 = time.perf_counter()
        try:
            yield rec
        except Exception as e:
            rec.error = f"{type(e).__name__}: {e}"
            ctx["force"] = True                     # luôn giữ trace có lỗi
            raise
        finally:
            rec.duration_ms = (time.perf_counter() - t0) * 1000
            ctx["stack"].pop()
            self.spans[ctx["trace_id"]].append(rec)
            if not ctx["stack"]:
                self._flush(ctx)

    def _flush(self, ctx: dict) -> None:
        tid = ctx["trace_id"]
        spans = self.spans.get(tid, [])
        total = max((s.duration_ms for s in spans if not s.parent_id), default=0)
        keep = ctx["sampled"] or ctx.get("force") or any(s.error for s in spans) \
            or total > 8000
        if keep:
            TRACE_DIR.mkdir(parents=True, exist_ok=True)
            path = TRACE_DIR / f"{datetime.now():%Y-%m-%d}.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "trace_id": tid, "tenant_id": ctx.get("tenant_id", ""),
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "total_ms": round(total, 1),
                    "spans": [{"span_id": s.span_id, "parent_id": s.parent_id,
                               "name": s.name, "ms": round(s.duration_ms, 1),
                               "attrs": redact(s.attrs), "error": s.error}
                              for s in spans]}, ensure_ascii=False, default=str) + "\n")
        self.spans.pop(tid, None)

    # ---- tiện ích ----
    def annotate(self, **attrs) -> None:
        ctx = _ctx.get({})
        if ctx and ctx["stack"]:
            tid, sid = ctx["trace_id"], ctx["stack"][-1]
            for s in self.spans.get(tid, []):
                if s.span_id == sid:
                    s.attrs.update(attrs)
                    return


tracer = Tracer(sample_rate=0.1)
```

`exercises/day68/traced_pipeline.py`:

```python
"""Ngày 68: gắn trace vào toàn bộ pipeline RAG."""
from leanai_core.tracing import tracer
from leanai_core.llm import LLMClient
from leanai_core.vectorstore import VectorStore
from leanai_core.hybrid import HybridSearch
from leanai_core.rerank import Reranker
from leanai_core.context_builder import ContextBuilder
from leanai_core.citation import CITED_SYSTEM, verify_citations

llm = LLMClient()
vs = VectorStore("company_kb")
hs = HybridSearch(vs); hs.build_bm25(where={"tenant_id": "clinic_001"})
rr = Reranker(llm)
cb = ContextBuilder(budget=3000)


def answer(question: str, tenant: str = "clinic_001") -> dict:
    tid = tracer.start_trace(tenant_id=tenant, force=True)
    W = {"tenant_id": tenant}

    with tracer.span("request", question=question[:100]):
        with tracer.span("retrieval", k=30) as s:
            with tracer.span("hybrid_search"):
                hits = hs.search(question, k=30, where=W)
            tracer.annotate(n_hits=len(hits),
                            top_score=round(hits[0].score, 3) if hits else 0)
            s.attrs["n_hits"] = len(hits)

        with tracer.span("rerank", model=llm.model):
            hits = rr.rerank(question, hits, top_k=8)
            tracer.annotate(n_after=len(hits))

        with tracer.span("context_build"):
            ctx = cb.build(hits)
            tracer.annotate(n_chunks=len(ctx.hits), tokens=ctx.tokens)

        with tracer.span("llm_answer") as s:
            docs = "\n".join(f'<document id="{i+1}">{h.text}</document>'
                             for i, h in enumerate(ctx.hits))
            r = llm.complete(f"<documents>\n{docs}\n</documents>\n\nCÂU HỎI: {question}",
                             system=CITED_SYSTEM, temperature=0, max_tokens=700)
            s.attrs.update(model=r.model, input_tokens=r.input_tokens,
                           output_tokens=r.output_tokens, cost=round(r.cost, 6))

        with tracer.span("verify"):
            check = verify_citations(r.text, ctx.hits)
            tracer.annotate(citation_ok=check.ok, confidence=check.confidence)

    return {"trace_id": tid, "answer": r.text, "check": check}


if __name__ == "__main__":
    out = answer("Khách huỷ lịch trước 24h có mất phí không?")
    print(out["answer"][:300])
    print(f"\ntrace_id = {out['trace_id']}")
    print("Xem chi tiết: python -m exercises.day69.trace_viewer", out["trace_id"])
```

---

## 4. Bài tập

**Bài 1 — Gắn trace toàn bộ.** Thêm span cho mọi tầng trong pipeline của bạn (guardrail, query rewrite, retrieval con, rerank, LLM, verify). Chạy 20 request.

**Bài 2 — Sampling.** Đặt `sample_rate=0.1`. Chạy 100 request trong đó 5 request lỗi và 3 request rất chậm. Kiểm tra: tất cả request lỗi và chậm **đều** được lưu, request bình thường chỉ ~10%.

**Bài 3 — Liên kết eval.** Sửa script eval (Ngày 67) để lưu `trace_id` cho mỗi case. Khi một case fail, in ra lệnh xem trace tương ứng.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 68 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Trace có cây span đúng cha-con, ≥ 6 tầng
- [ ] Span LLM ghi đủ model, token, cost
- [ ] Sampling giữ 100% request lỗi và chậm
- [ ] Không có dữ liệu nhạy cảm trong trace (redact hoạt động)
- [ ] Eval case gắn được trace_id
- [ ] Quiz ≥ 80%
