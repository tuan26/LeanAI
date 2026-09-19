# NGÀY 50 — PROJECT #2: Company Knowledge AI

> Phase 3 · Cả ngày. **Project thứ 2 vào portfolio** — và là trái tim kỹ thuật của CareDesk-AI.

## 🎯 Mục tiêu

Hệ thống hỏi–đáp tài liệu doanh nghiệp hoàn chỉnh, **được đánh giá trên 100 câu hỏi** với 6 chỉ số.

---

## 1. Đặc tả

```
Nạp tài liệu:  python -m leanai_core.ingest --dir data/docs --tenant clinic_001
Hỏi:           python -m projects.p2.ask "chính sách hoàn tiền thế nào?" --tenant clinic_001
Đánh giá:      python -m projects.p2.evaluate --testset data/testset-100.json
```

### Kiến trúc bắt buộc

```
Tài liệu (PDF/Word/Excel)
   ↓ ingest: parse → quality gate → injection scan → chunk → enrich → index tăng dần
Vector DB (tenant-scoped)
   ↓
Câu hỏi → chuẩn hoá → router viết lại → hybrid search (k=30) → rerank (→5)
   ↓ context builder (ngân sách + khử trùng + sắp xếp)
LLM (T=0, bắt trích dẫn, có chế độ PARTIAL)
   ↓ verify citations (3 tầng) + groundedness
Câu trả lời + nguồn + confidence
```

Mỗi mũi tên là một ngày bạn đã học. Hôm nay chỉ ghép lại.

### 6 chỉ số phải báo cáo

| Chỉ số | Mục tiêu |
|---|---|
| Retrieval recall@5 | ≥ 0.85 |
| Answer accuracy | ≥ 0.80 |
| Citation accuracy | ≥ 0.90 |
| Hallucination rate | < 0.05 |
| Latency p50 / p95 | < 3s / < 8s |
| Cost per query | ghi rõ, so sánh các cấu hình |

---

## 2. Bộ test 100 câu

`data/testset-100.json`:

```jsonc
[
  {"id": "q001",
   "question": "Khách huỷ lịch trước 24h có mất phí không?",
   "kind": "answerable",              // answerable|unanswerable|false_premise|multi_hop|numeric
   "expected": "Không mất phí nếu huỷ trước 24 giờ",
   "relevant_doc_ids": ["chinh-sach.pdf#chunk2"],
   "difficulty": "easy"}
]
```

**Phân bố bắt buộc:**

| Loại | Số câu | Mục đích |
|---|---|---|
| answerable — dễ | 30 | baseline |
| answerable — diễn đạt khác | 25 | test embedding |
| multi_hop (cần ≥ 2 tài liệu) | 15 | test truy hồi + tổng hợp |
| numeric (giá, ngày, %) | 10 | test chống bịa số |
| unanswerable | 15 | test từ chối |
| false_premise | 5 | test phản biện |

Xây bộ này mất 2–3 giờ. **Đừng cắt bớt** — nó là thứ phân biệt bạn với người chỉ xem tutorial.

---

## 3. Script đánh giá

`projects/p2-company-knowledge-rag/evaluate.py`:

```python
"""Đánh giá RAG trên 100 câu, 6 chỉ số."""
import argparse, json, statistics, time
from pathlib import Path

from leanai_core.llm import LLMClient
from leanai_core.vectorstore import VectorStore
from leanai_core.hybrid import HybridSearch
from leanai_core.rerank import Reranker
from leanai_core.context_builder import ContextBuilder
from leanai_core.embedding import EmbeddingService
from leanai_core.citation import CITED_SYSTEM, verify_citations
from leanai_core.groundedness import check_groundedness
from leanai_core.retrieval_eval import recall_at_k

JUDGE = """<câu_hỏi>{q}</câu_hỏi>
<đáp_án_chuẩn>{gold}</đáp_án_chuẩn>
<câu_trả_lời>{a}</câu_trả_lời>

Câu trả lời có đúng về NỘI DUNG so với đáp án chuẩn không?
CHỈ trả về một từ: ĐÚNG | SAI | TỪ_CHỐI"""


def run(testset: str, tenant: str, collection: str, use_rerank: bool = True) -> dict:
    llm, emb = LLMClient(), EmbeddingService()
    vs = VectorStore(collection, embedder=emb)
    hs = HybridSearch(vs); hs.build_bm25(where={"tenant_id": tenant})
    rr = Reranker(llm)
    cb = ContextBuilder(budget=3000, embedder=emb)
    cases = json.loads(Path(testset).read_text(encoding="utf-8"))
    W = {"tenant_id": tenant}

    rec, acc, cit, hall, lat, cost = [], [], [], [], [], []
    by_kind: dict[str, list[int]] = {}
    failures = []

    for i, c in enumerate(cases, 1):
        t0 = time.time()
        hits = hs.search(c["question"], k=30, where=W)
        if use_rerank:
            hits = rr.rerank(c["question"], hits, top_k=8)
        ctx = cb.build(hits)

        got_ids = [f"{h.meta['doc_id']}#chunk{h.meta.get('chunk_index',0)}" for h in ctx.hits]
        rec.append(recall_at_k(got_ids, c.get("relevant_doc_ids", []), 5))

        docs = "\n".join(f'<document id="{j+1}" source="{h.meta.get("doc_id")}">\n{h.text}\n</document>'
                         for j, h in enumerate(ctx.hits))
        r = llm.complete(f"<documents>\n{docs}\n</documents>\n\nCÂU HỎI: {c['question']}",
                         system=CITED_SYSTEM, temperature=0, max_tokens=700, tag="answer")
        lat.append(time.time() - t0); cost.append(r.cost)

        check = verify_citations(r.text, ctx.hits)
        cit.append(1 if check.ok else 0)

        refused = "KHÔNG ĐỦ THÔNG TIN" in r.text.upper()
        if c["kind"] in ("unanswerable", "false_premise"):
            correct = refused
            hall.append(0 if refused else 1)
        else:
            v = llm.complete(JUDGE.format(q=c["question"], gold=c.get("expected", ""), a=r.text),
                             temperature=0, max_tokens=10, tag="judge").text.upper()
            correct = "ĐÚNG" in v
            g = check_groundedness(llm, r.text, ctx.hits) if not refused else None
            hall.append(1 if (check.ghost_numbers or (g and g.unsupported)) else 0)
        acc.append(1 if correct else 0)
        by_kind.setdefault(c["kind"], []).append(1 if correct else 0)
        if not correct:
            failures.append({"id": c["id"], "q": c["question"], "kind": c["kind"],
                             "answer": r.text[:200], "recall": rec[-1]})
        if i % 10 == 0:
            print(f"  ...{i}/{len(cases)}")

    def avg(x): return sum(x) / len(x)
    return {
        "recall@5": avg(rec), "answer_accuracy": avg(acc),
        "citation_accuracy": avg(cit), "hallucination_rate": avg(hall),
        "latency_p50": statistics.median(lat),
        "latency_p95": sorted(lat)[int(len(lat) * 0.95) - 1],
        "cost_per_query": avg(cost), "total_cost": sum(cost),
        "by_kind": {k: avg(v) for k, v in by_kind.items()},
        "failures": failures, "usage": llm.usage.report(),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--testset", default="data/testset-100.json")
    ap.add_argument("--tenant", default="clinic_001")
    ap.add_argument("--collection", default="company_kb")
    ap.add_argument("--no-rerank", action="store_true")
    a = ap.parse_args()

    r = run(a.testset, a.tenant, a.collection, use_rerank=not a.no_rerank)

    print("\n" + "=" * 62)
    print(f"{'CHỈ SỐ':<24}{'GIÁ TRỊ':>12}{'MỤC TIÊU':>14}{'':>6}")
    targets = {"recall@5": 0.85, "answer_accuracy": 0.80,
               "citation_accuracy": 0.90, "hallucination_rate": 0.05}
    for k, t in targets.items():
        v = r[k]
        ok = v <= t if "hallucination" in k else v >= t
        print(f"{k:<24}{v:>12.3f}{t:>14}{'  ✓' if ok else '  ✗'}")
    print(f"{'latency p50':<24}{r['latency_p50']:>12.2f}s{'<3s':>13}")
    print(f"{'latency p95':<24}{r['latency_p95']:>12.2f}s{'<8s':>13}")
    print(f"{'cost/query':<24}${r['cost_per_query']:>11.5f}")
    print(f"{'tổng chi phí':<24}${r['total_cost']:>11.4f}")

    print("\nĐộ chính xác theo loại câu hỏi:")
    for k, v in sorted(r["by_kind"].items(), key=lambda x: x[1]):
        print(f"  {k:<22} {v:.2f}{'  ⚠' if v < 0.7 else ''}")

    print(f"\n{len(r['failures'])} ca thất bại — 10 ca đầu:")
    for f in r["failures"][:10]:
        print(f"  [{f['id']}] ({f['kind']}, recall={f['recall']:.1f}) {f['q'][:55]}")

    Path("projects/p2-company-knowledge-rag/EVAL.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nĐã lưu EVAL.json")
```

---

## 4. Việc phải làm

1. Xây bộ test 100 câu (2–3 giờ).
2. Chạy `evaluate.py` → **baseline**.
3. Chạy thêm 3 cấu hình: không rerank / không hybrid / chunk khác. Lập bảng so sánh.
4. Phân tích 10 ca thất bại tệ nhất, sửa **một** thứ, đo lại.
5. Viết `README.md` cho project: kiến trúc, cấu hình chọn, bảng kết quả, hạn chế đã biết.

---

## 5. PASS/FAIL

- [ ] Bộ test 100 câu đúng phân bố 6 loại
- [ ] Đạt cả 4 chỉ số mục tiêu (recall ≥ 0.85, accuracy ≥ 0.80, citation ≥ 0.90, bịa < 0.05)
- [ ] p95 latency < 8s
- [ ] Có bảng so sánh ≥ 4 cấu hình
- [ ] Có phân tích ≥ 10 ca thất bại kèm nguyên nhân
- [ ] Một vòng cải tiến có số liệu trước/sau
- [ ] README đủ để người khác chạy lại

---

## 6. Tổng kết Phase 3

```powershell
python quiz\quiz.py --day 50
python quiz\quiz.py --exam 31 50
python quiz\quiz.py --stats
git add . ; git commit -m "day 50: Company Knowledge AI - Phase 3 complete"
```

`progress/notes/phase3-review.md`: cấu hình RAG cuối cùng (embedding model, chunk size, k, rerank), 3 kỹ thuật tác dụng nhất, chi phí Phase 3, và **điều bạn sẽ nói với khách hàng về giới hạn của RAG**.

> **Nhìn trước Phase 4:** 15 ngày Agent. Chuyển từ "AI trả lời" sang "AI làm việc".
