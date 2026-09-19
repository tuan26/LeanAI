# NGÀY 44 — Ingestion pipeline (1 lệnh)

> Phase 3 · Cả buổi. Ghép Ngày 38–43 thành một lệnh duy nhất.

## 🎯 Mục tiêu

```powershell
python -m leanai_core.ingest --dir data/docs --tenant clinic_001
```

Quét thư mục → parse mọi định dạng → kiểm chất lượng → quét injection → chunk → làm giàu → index tăng dần → báo cáo.

---

## 1. Thiết kế pipeline (20 phút)

```
Thư mục
   │
   ├─► [1] Liệt kê file        (bỏ file tạm ~$, .DS_Store, file quá lớn)
   ├─► [2] Parse               (pdf/docx/xlsx/txt/md → ParsedDoc)
   ├─► [3] Kiểm chất lượng     (quality < ngưỡng → quarantine, KHÔNG index)
   ├─► [4] Quét an ninh        (injection ẩn → quarantine + cảnh báo)
   ├─► [5] Chunk               (chiến lược đã chọn ở Ngày 41)
   ├─► [6] Làm giàu metadata   (Ngày 42)
   ├─► [7] Index tăng dần      (Ngày 43)
   └─► [8] Báo cáo             (bảng: file, trạng thái, chunk, chi phí, lý do bỏ)
```

**Nguyên tắc:** pipeline **không bao giờ dừng vì một file lỗi**. Ghi lỗi, chuyển sang file tiếp theo, báo cáo cuối cùng.

---

## 2. Thực hành (100 phút)

`leanai_core/ingest.py`:

```python
"""Pipeline ingest hoàn chỉnh — một lệnh cho cả thư mục."""
from __future__ import annotations

import argparse
import shutil
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from .chunking import chunk_by_section, chunk_recursive
from .embedding import EmbeddingService
from .enrich import build_meta, contextualize, summarize_doc
from .indexer import Indexer, IngestState
from .llm import LLMClient
from .logging import log_event
from .parsers.excel import parse_excel
from .parsers.pdf import parse_pdf, scan_for_injection
from .parsers.word import parse_docx
from .vectorstore import VectorStore, Chunk

SUPPORTED = {".pdf", ".docx", ".xlsx", ".txt", ".md"}
MAX_FILE_MB = 50
MIN_QUALITY = 0.3


@dataclass
class FileResult:
    path: Path
    status: str = "ok"          # ok | skipped | quarantined | error
    reason: str = ""
    chunks: int = 0
    added: int = 0
    kept: int = 0
    removed: int = 0
    seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)


class IngestPipeline:
    def __init__(self, collection: str, tenant_id: str, *,
                 contextual: bool = False, quarantine_dir: str = "data/quarantine"):
        self.emb = EmbeddingService()
        self.vs = VectorStore(collection, embedder=self.emb)
        self.ix = Indexer(self.vs, IngestState())
        self.llm = LLMClient() if contextual else None
        self.tenant = tenant_id
        self.contextual = contextual
        self.quarantine = Path(quarantine_dir)

    # ---------- [2] parse ----------
    def _parse(self, p: Path):
        if p.suffix == ".pdf":
            d = parse_pdf(p)
            return d.full_text, None, d.warnings, d.quality, scan_for_injection(d)
        if p.suffix == ".docx":
            d = parse_docx(p)
            return d.full_text, d.sections(), d.warnings, 1.0, []
        if p.suffix == ".xlsx":
            sheets = parse_excel(p)
            texts, warns = [], []
            for s in sheets:
                if s.skipped_reason:
                    warns.append(f"sheet '{s.name}': {s.skipped_reason}")
                texts.extend(s.texts)
            return "\n\n".join(texts), None, warns, 1.0 if texts else 0.0, []
        text = p.read_text(encoding="utf-8", errors="replace")
        return text, None, [], 1.0 if text.strip() else 0.0, []

    def _quarantine(self, p: Path, reason: str) -> None:
        self.quarantine.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, self.quarantine / p.name)
        (self.quarantine / f"{p.name}.reason.txt").write_text(reason, encoding="utf-8")

    def ingest_file(self, p: Path) -> FileResult:
        r = FileResult(path=p)
        t0 = time.time()
        try:
            if p.suffix.lower() not in SUPPORTED:
                r.status, r.reason = "skipped", f"định dạng {p.suffix} chưa hỗ trợ"
                return r
            if p.stat().st_size > MAX_FILE_MB * 1024 * 1024:
                r.status, r.reason = "skipped", f"file > {MAX_FILE_MB}MB"
                return r

            text, sections, warns, quality, injections = self._parse(p)
            r.warnings = warns

            if injections:
                r.status = "quarantined"
                r.reason = f"phát hiện {len(injections)} chỉ dẫn ẩn nghi injection"
                self._quarantine(p, r.reason + "\n" + "\n".join(injections))
                return r
            if quality < MIN_QUALITY or not text.strip():
                r.status = "quarantined"
                r.reason = f"chất lượng parse thấp ({quality})"
                self._quarantine(p, r.reason)
                return r

            # [5] chunk
            tc = (chunk_by_section(sections, 800) if sections
                  else chunk_recursive(text, 600, 100))
            r.chunks = len(tc)

            # [6] làm giàu
            doc_sum = ""
            if self.contextual and self.llm:
                doc_sum = summarize_doc(self.llm, text)

            chunks = []
            for c in tc:
                body = c.text
                if doc_sum and self.llm:
                    body = contextualize(self.llm, c.text, doc_sum) + "\n\n" + c.text
                meta = build_meta(tenant_id=self.tenant, path=p, chunk_index=c.index,
                                  text=body, section=c.meta.get("section", ""))
                chunks.append(Chunk(text=body, meta=meta.to_payload()))

            # [7] index tăng dần
            res = self.ix.index_doc(self.tenant, p.name, chunks, source_path=p)
            if res.skipped:
                r.status, r.reason = "skipped", "file không đổi kể từ lần ingest trước"
            r.added, r.kept, r.removed = res.added, res.kept, res.removed

        except Exception as e:
            r.status = "error"
            r.reason = f"{type(e).__name__}: {e}"
            log_event("ingest_error", file=str(p), error=r.reason,
                      trace=traceback.format_exc()[:1000])
        finally:
            r.seconds = time.time() - t0
        return r

    def ingest_dir(self, d: Path) -> list[FileResult]:
        files = [f for f in sorted(d.rglob("*"))
                 if f.is_file() and not f.name.startswith(("~$", "."))]
        out = []
        for i, f in enumerate(files, 1):
            print(f"[{i}/{len(files)}] {f.name} ...", end=" ", flush=True)
            r = self.ingest_file(f)
            icon = {"ok": "✓", "skipped": "⏭", "quarantined": "🚫", "error": "✗"}[r.status]
            print(f"{icon} {r.status} (+{r.added}/={r.kept}/-{r.removed}) {r.reason}")
            out.append(r)
        return out


def report(results: list[FileResult], pipeline: IngestPipeline) -> None:
    print("\n" + "=" * 78)
    print(f"{'file':<34} {'trạng thái':<12} {'chunk':>6} {'+':>4} {'=':>4} {'-':>4} {'giây':>6}")
    print("-" * 78)
    for r in results:
        print(f"{r.path.name[:33]:<34} {r.status:<12} {r.chunks:>6} "
              f"{r.added:>4} {r.kept:>4} {r.removed:>4} {r.seconds:>6.1f}")
    ok = sum(1 for r in results if r.status == "ok")
    q = [r for r in results if r.status == "quarantined"]
    err = [r for r in results if r.status == "error"]
    print("-" * 78)
    print(f"Thành công {ok}/{len(results)} | cách ly {len(q)} | lỗi {len(err)} | "
          f"tổng chunk thêm {sum(r.added for r in results)}")
    for r in q + err:
        print(f"  ⚠ {r.path.name}: {r.reason}")
    print(f"\n{pipeline.emb.stats()}")
    if pipeline.llm:
        print(pipeline.llm.usage.report())
    print("\nKiểm tra bất biến:", pipeline.ix.verify(pipeline.tenant))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--collection", default="company_kb")
    ap.add_argument("--contextual", action="store_true",
                    help="bật contextual retrieval (tốn LLM, xem Ngày 42)")
    a = ap.parse_args()

    pipe = IngestPipeline(a.collection, a.tenant, contextual=a.contextual)
    res = pipe.ingest_dir(Path(a.dir))
    report(res, pipe)
```

---

## 3. Việc phải làm

1. **Chuẩn bị `data/docs/`** với ít nhất 15 file thật: PDF text, PDF scan, Word có heading, Excel bảng giá, Excel 1000 dòng dữ liệu, file lỗi/rỗng, file có injection ẩn.
2. **Chạy lần 1** — xem báo cáo. Mọi file phải được xử lý hoặc từ chối **có lý do rõ ràng**.
3. **Chạy lần 2 ngay** — tất cả phải `skipped`, 0 chunk thêm mới, gần như không tốn tiền.
4. **Sửa 1 file rồi chạy lại** — chỉ file đó được xử lý, chỉ phần thay đổi được embed.

---

## 4. PASS/FAIL

- [ ] Một lệnh xử lý cả thư mục, không dừng khi gặp file lỗi
- [ ] File chất lượng thấp và file có injection bị cách ly, **không vào index**
- [ ] Chạy lần 2: 100% skipped, chi phí ≈ 0
- [ ] Sửa 1 file: chỉ file đó bị xử lý lại
- [ ] Báo cáo cuối có đủ: trạng thái, số chunk, lý do, chi phí, kiểm tra bất biến
- [ ] `verify()`: trùng lặp = 0, mồ côi = 0

---

## 5. Quiz + tổng kết tuần 7

```powershell
python quiz\quiz.py --day 44
python quiz\quiz.py --exam 38 44
git add . ; git commit -m "day 44: ingestion pipeline hoàn chỉnh"
```

Ghi `progress/notes/week7-review.md`: loại file nào khó nhất, tỉ lệ file bị từ chối, và **bạn sẽ nói gì với khách hàng** khi 30% tài liệu của họ là PDF scan.
