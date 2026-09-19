# NGÀY 81 — Tenant-scoped RAG

> Phase 6 · 15' thiết kế — 105' code

## 🎯 Mục tiêu

Mỗi phòng khám có kho tri thức riêng: bảng giá, chính sách, quy trình — và AI chỉ dùng tài liệu của đúng phòng khám đó.

---

## 1. Thiết kế (15 phút)

### Vì sao cần RAG trong CareDesk-AI

| Không có RAG | Có RAG |
|---|---|
| Tin nhắn chỉ nói chung chung | Nhắc đúng chính sách của phòng khám đó |
| Nhân viên phải tự tra bảng giá | Hỏi AI, có nguồn |
| AI không biết quy trình nội bộ | Trả lời theo đúng quy trình đã duyệt |

### Kiến trúc

```
Mỗi tenant upload tài liệu
  → ingest pipeline (Ngày 44) với tenant_id
  → cùng collection Qdrant, tách bằng filter + payload index
  → mọi search đi qua TenantKB (Ngày 80)
```

> Dùng **một collection + filter** cho đến ~50 tenant. Khách hàng yêu cầu cách ly vật lý → tạo collection riêng theo tenant, chỉ cần đổi trong `TenantKB`.

---

## 2. Code (105 phút)

`backend/app/models.py` — thêm bảng documents:

```python
class Document(Base, TenantMixin):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(300))
    doc_type: Mapped[str] = mapped_column(String(40), default="other")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | indexed | quarantined | failed
    n_chunks: Mapped[int] = mapped_column(Integer, default=0)
    quality: Mapped[float] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    uploaded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_hash: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

`backend/app/routers/documents.py`:

```python
"""Upload và quản lý tài liệu tri thức của tenant."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..deps import Principal, require_permission
from ..db import tenant_session
from ..models import Document
from ..services.ingest import ingest_upload

router = APIRouter(prefix="/documents", tags=["documents"])
MAX_MB = 20
ALLOWED = {".pdf", ".docx", ".xlsx", ".txt", ".md"}


@router.post("")
async def upload(file: UploadFile = File(...),
                 p: Principal = Depends(require_permission("import_data"))):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Định dạng {ext} không được hỗ trợ")
    content = await file.read()
    if len(content) > MAX_MB * 1024 * 1024:
        raise HTTPException(400, f"File vượt {MAX_MB}MB")

    result = ingest_upload(tenant_id=p.tenant_id, filename=file.filename,
                           content=content, user_id=p.user_id)
    if result["status"] == "quarantined":
        raise HTTPException(422, {"message": "Tài liệu bị từ chối", **result})
    return result


@router.get("")
def list_documents(p: Principal = Depends(require_permission("read_customers"))):
    with tenant_session(p.tenant_id) as db:
        docs = db.query(Document).order_by(Document.created_at.desc()).all()
        return [{"id": d.id, "filename": d.filename, "status": d.status,
                 "n_chunks": d.n_chunks, "quality": d.quality, "error": d.error}
                for d in docs]


@router.delete("/{doc_id}")
def delete_document(doc_id: int,
                    p: Principal = Depends(require_permission("import_data"))):
    from ..services.kb import TenantKB
    with tenant_session(p.tenant_id) as db:
        d = db.query(Document).filter(Document.id == doc_id).first()
        if not d:
            raise HTTPException(404, "Không tìm thấy tài liệu")
        TenantKB(p.tenant_id).delete_doc(d.filename)
        db.delete(d)
    return {"status": "deleted"}
```

`backend/app/services/ingest.py` — nối pipeline Ngày 44:

```python
"""Ingest tài liệu cho một tenant."""
import tempfile
from pathlib import Path

from leanai_core.chunking import chunk_by_section, chunk_recursive
from leanai_core.enrich import build_meta
from leanai_core.indexer import Indexer, IngestState, file_hash
from leanai_core.parsers.pdf import parse_pdf, scan_for_injection
from leanai_core.parsers.word import parse_docx
from leanai_core.parsers.excel import parse_excel
from leanai_core.vectorstore import Chunk

from ..db import tenant_session
from ..models import Document
from .kb import TenantKB

MIN_QUALITY = 0.3


def ingest_upload(*, tenant_id: str, filename: str, content: bytes,
                  user_id: int | None = None) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / filename
        path.write_bytes(content)
        fhash = file_hash(path)

        with tenant_session(tenant_id) as db:
            existing = db.query(Document).filter(
                Document.filename == filename).first()
            if existing and existing.file_hash == fhash:
                return {"status": "skipped", "reason": "file không đổi",
                        "document_id": existing.id}

        # parse
        warnings, injections, quality, sections = [], [], 1.0, None
        if path.suffix == ".pdf":
            d = parse_pdf(path)
            text, warnings, quality = d.full_text, d.warnings, d.quality
            injections = scan_for_injection(d)
        elif path.suffix == ".docx":
            d = parse_docx(path)
            text, sections, warnings = d.full_text, d.sections(), d.warnings
        elif path.suffix == ".xlsx":
            sheets = parse_excel(path)
            text = "\n\n".join(t for s in sheets for t in s.texts)
            warnings = [s.skipped_reason for s in sheets if s.skipped_reason]
            quality = 1.0 if text.strip() else 0.0
        else:
            text = path.read_text(encoding="utf-8", errors="replace")

        status, error = "indexed", ""
        if injections:
            status, error = "quarantined", f"phát hiện chỉ dẫn ẩn: {injections[0][:120]}"
        elif quality < MIN_QUALITY or not text.strip():
            status, error = "quarantined", f"chất lượng parse thấp ({quality})"

        n_chunks = 0
        if status == "indexed":
            tc = chunk_by_section(sections, 800) if sections else chunk_recursive(text, 600, 100)
            chunks = [Chunk(text=c.text,
                            meta=build_meta(tenant_id=tenant_id, path=path,
                                            chunk_index=c.index, text=c.text,
                                            section=c.meta.get("section", "")).to_payload())
                      for c in tc]
            kb = TenantKB(tenant_id)
            res = Indexer(kb.vs, IngestState()).index_doc(tenant_id, filename, chunks,
                                                          source_path=path)
            n_chunks = len(chunks)

        with tenant_session(tenant_id) as db:
            doc = db.query(Document).filter(Document.filename == filename).first() \
                  or Document(tenant_id=tenant_id, filename=filename)
            doc.status, doc.error = status, error
            doc.n_chunks, doc.quality, doc.file_hash = n_chunks, quality, fhash
            doc.uploaded_by = user_id
            db.add(doc)
            db.flush()
            doc_id = doc.id

        return {"status": status, "document_id": doc_id, "n_chunks": n_chunks,
                "quality": quality, "warnings": warnings, "error": error}
```

`backend/app/routers/ask.py` — hỏi đáp tài liệu:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import Principal, require_permission
from ..services.kb import TenantKB
from leanai_core.llm import LLMClient
from leanai_core.citation import CITED_SYSTEM, verify_citations, render_sources
from leanai_core.context_builder import ContextBuilder

router = APIRouter(prefix="/ask", tags=["ask"])
llm = LLMClient()
cb = ContextBuilder(budget=3000)


class AskIn(BaseModel):
    question: str


@router.post("")
def ask(body: AskIn, p: Principal = Depends(require_permission("read_customers"))):
    kb = TenantKB(p.tenant_id)
    ctx = cb.build(kb.search(body.question, k=20))
    if not ctx.hits:
        return {"answer": "KHÔNG ĐỦ THÔNG TIN — chưa có tài liệu liên quan.",
                "sources": [], "confidence": "NONE"}

    docs = "\n".join(f'<document id="{i+1}" source="{h.meta.get("doc_id")}">\n{h.text}\n</document>'
                     for i, h in enumerate(ctx.hits))
    r = llm.complete(f"<documents>\n{docs}\n</documents>\n\nCÂU HỎI: {body.question}",
                     system=CITED_SYSTEM, temperature=0, max_tokens=700, tag="ask")
    check = verify_citations(r.text, ctx.hits)
    if check.confidence == "BLOCKED":
        return {"answer": "Không thể xác minh câu trả lời. Vui lòng hỏi nhân viên phụ trách.",
                "sources": [], "confidence": "BLOCKED", "problems": check.problems()}
    import re
    cited = sorted({int(x) for x in re.findall(r"\[(\d+)\]", r.text)})
    return {"answer": r.text, "sources": render_sources(ctx.hits, cited).splitlines(),
            "confidence": check.confidence, "cost": round(r.cost, 6)}
```

---

## 3. Việc phải làm

1. Upload **5 tài liệu cho clinic_001** và **3 tài liệu khác cho clinic_002**.
2. Hỏi 10 câu ở mỗi tenant, kiểm tra: **không bao giờ** trả lời bằng tài liệu của tenant kia.
3. Upload một file có injection ẩn → phải bị cách ly.
4. Upload lại file cũ không đổi → phải `skipped`.

---

## 4. PASS/FAIL

- [ ] Upload → ingest → hỏi đáp chạy end-to-end
- [ ] Tài liệu chất lượng thấp / có injection bị cách ly, không vào index
- [ ] 20 câu hỏi × 2 tenant: 0 lần rò rỉ chéo
- [ ] Mọi câu trả lời có nguồn hiển thị được
- [ ] Câu trả lời có số liệu không xác minh được → bị chặn
- [ ] Upload lại file không đổi → skipped, chi phí ≈ 0

---

## 5. Quiz + commit

```powershell
python quiz\quiz.py --day 81 ; python quiz\quiz.py --review
git add . ; git commit -m "day 81: tenant-scoped RAG"
```
