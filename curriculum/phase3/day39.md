# NGÀY 39 — Word parsing

> Phase 3 · 15' lý thuyết — 10' tài liệu — 85' code — 10' note

## 🎯 Mục tiêu

Trích Word **giữ được cấu trúc heading** — vì heading là metadata miễn phí và cực kỳ giá trị cho chunking.

---

## 1. Lý thuyết cốt lõi (15 phút)

### 1.1 Word tốt hơn PDF ở điểm nào

`.docx` là file ZIP chứa XML — cấu trúc còn nguyên vẹn:

```
Heading 1  →  "3. Chính sách hoàn tiền"
Heading 2  →  "3.2 Điều kiện áp dụng"
Paragraph  →  "Khách hàng được hoàn 80%..."
Table      →  bảng giá
List       →  danh sách điều kiện
```

PDF là "ảnh chụp" của layout — cấu trúc đã mất. **Nếu khách hàng có cả bản Word, luôn ưu tiên Word.**

### 1.2 Vì sao heading quý

```
chunk.text = "Khách hàng được hoàn 80% giá trị buổi chưa dùng."
chunk.meta["section_path"] = "Chính sách 2026 > 3. Hoàn tiền > 3.2 Điều kiện"
```

Lợi ích:
1. **Trích dẫn chính xác** — nói được điều khoản nào, không chỉ "trang 5".
2. **Chunk đúng ranh giới ngữ nghĩa** — cắt theo heading thay vì cắt mù theo số ký tự (Ngày 41).
3. **Ngữ cảnh cho embedding** — thêm section_path vào text trước khi embed giúp chunk ngắn vẫn có ngữ cảnh.

### 1.3 Những thứ dễ bỏ sót trong .docx

| Thành phần | Có quan trọng không |
|---|---|
| Bảng | ✅ thường chứa bảng giá |
| Header/footer | ⚠️ thường là nhiễu |
| Comment, track changes | ⚠️ có thể chứa nội dung chưa duyệt — **cẩn thận** |
| Text box, shape | ✅ hay chứa ghi chú quan trọng |
| Footnote | ✅ hay chứa điều kiện ràng buộc |

> Track changes chưa chấp nhận = nội dung **chưa được duyệt**. Index nhầm sẽ khiến AI trả lời theo bản nháp.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| python-docx | https://python-docx.readthedocs.io/ |
| Office Open XML (tham khảo) | http://officeopenxml.com/WPcontentOverview.php |

---

## 3. Thực hành (85 phút)

```powershell
pip install python-docx
```

`leanai_core/parsers/word.py`:

```python
"""Parser Word giữ cấu trúc heading."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


@dataclass
class Block:
    text: str
    level: int = 0                 # 0 = đoạn văn, 1-6 = heading
    section_path: str = ""
    block_type: str = "paragraph"  # paragraph | heading | table | list


@dataclass
class ParsedDocx:
    path: str
    blocks: list[Block]
    warnings: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)

    def sections(self) -> dict[str, str]:
        """Gom nội dung theo section_path — dùng trực tiếp cho chunking."""
        out: dict[str, list[str]] = {}
        for b in self.blocks:
            if b.block_type != "heading":
                out.setdefault(b.section_path, []).append(b.text)
        return {k: "\n".join(v) for k, v in out.items() if v}


def _iter_block_items(doc):
    """Duyệt đoạn văn VÀ bảng theo đúng thứ tự trong tài liệu."""
    from docx.oxml.ns import qn
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def _table_md(tbl: Table) -> str:
    rows = [[c.text.strip().replace("\n", " ") for c in r.cells] for r in tbl.rows]
    if not rows:
        return ""
    md = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]
    md += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(md)


def parse_docx(path: str | Path) -> ParsedDocx:
    path = Path(path)
    doc = Document(str(path))
    blocks: list[Block] = []
    warnings: list[str] = []
    stack: list[str] = []              # ngăn xếp heading hiện tại

    title = path.stem
    try:
        if doc.core_properties.title:
            title = doc.core_properties.title
    except Exception:
        pass
    stack.append(title)

    for item in _iter_block_items(doc):
        if isinstance(item, Table):
            md = _table_md(item)
            if md:
                blocks.append(Block(text=md, section_path=" > ".join(stack),
                                    block_type="table"))
            continue

        text = item.text.strip()
        if not text:
            continue
        style = (item.style.name or "").lower()

        m = re.match(r"heading (\d)", style)
        if m:
            lvl = int(m.group(1))
            stack = stack[:lvl] + [text]
            blocks.append(Block(text=text, level=lvl,
                                section_path=" > ".join(stack), block_type="heading"))
        elif "list" in style:
            blocks.append(Block(text=text, section_path=" > ".join(stack),
                                block_type="list"))
        else:
            blocks.append(Block(text=text, section_path=" > ".join(stack)))

    # cảnh báo track changes / comment
    xml = doc.element.xml
    if "w:ins " in xml or "w:del " in xml:
        warnings.append("CÓ TRACK CHANGES chưa chấp nhận — nội dung có thể là bản nháp")
    if not any(b.block_type == "heading" for b in blocks):
        warnings.append("không có heading — tài liệu phẳng, chunking sẽ kém chính xác")

    return ParsedDocx(path=str(path), blocks=blocks, warnings=warnings)
```

`exercises/day39/word_test.py`:

```python
from pathlib import Path
from leanai_core.parsers.word import parse_docx

for f in sorted(Path("data/docs").glob("*.docx")):
    d = parse_docx(f)
    print(f"\n{'='*70}\n{f.name}")
    print(f"  {len(d.blocks)} block | "
          f"{sum(1 for b in d.blocks if b.block_type=='heading')} heading | "
          f"{sum(1 for b in d.blocks if b.block_type=='table')} bảng")
    for w in d.warnings:
        print(f"  ⚠ {w}")
    print("  --- Cây mục lục ---")
    for b in d.blocks:
        if b.block_type == "heading":
            print("    " + "  " * (b.level - 1) + f"[{b.level}] {b.text[:60]}")
    print("  --- Section có nội dung ---")
    for path_, content in list(d.sections().items())[:5]:
        print(f"    {path_[:70]}  ({len(content)} ký tự)")
```

---

## 4. Bài tập

**Bài 1 — So sánh Word vs PDF.** Lấy **cùng một tài liệu** ở cả 2 định dạng. So sánh: số ký tự trích được, có giữ heading không, bảng có đúng không. Ghi kết luận — bạn sẽ dùng nó để thuyết phục khách hàng gửi file gốc.

**Bài 2 — Section path vào embedding.** Với mỗi section, tạo 2 phiên bản text: (a) chỉ nội dung, (b) `"{section_path}\n{nội dung}"`. Embed cả hai, chạy 10 truy vấn. Phiên bản nào recall tốt hơn? Ghi số liệu.

**Bài 3 — Parser thống nhất.** Viết `leanai_core/parsers/__init__.py` với `parse_any(path) -> ParsedDoc` tự chọn parser theo đuôi file (.pdf/.docx/.txt/.md), trả về **cùng một cấu trúc**. Đây là nền cho pipeline Ngày 44.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 39 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Trích được đoạn văn, bảng, danh sách **đúng thứ tự** trong tài liệu
- [ ] `section_path` đúng cho mọi block
- [ ] Cảnh báo được track changes
- [ ] Có số liệu chứng minh section_path cải thiện recall
- [ ] `parse_any` hoạt động cho ≥ 3 định dạng
- [ ] Quiz ≥ 80%
