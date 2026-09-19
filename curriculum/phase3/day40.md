# NGÀY 40 — Excel parsing

> Phase 3 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Biến bảng tính thành text **có ngữ nghĩa** — và biết khi nào **không nên** đưa Excel vào RAG.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vấn đề cốt lõi: Excel không phải văn bản

```
| Dịch vụ        | Giá     | Số buổi | Hạn dùng |
| Trị liệu da    | 12000000| 10      | 6 tháng  |
```

Nếu chunk thành `"Trị liệu da 12000000 10 6 tháng"` → embedding gần như vô nghĩa, và LLM không biết `10` là số buổi hay số tháng.

### 1.2 Bốn chiến lược chuyển bảng thành text

| Chiến lược | Ví dụ | Dùng khi |
|---|---|---|
| **Row-to-sentence** ⭐ | "Dịch vụ *Trị liệu da*: giá 12.000.000đ, gồm 10 buổi, hạn dùng 6 tháng." | bảng danh mục, mỗi dòng độc lập |
| **Markdown table** | giữ nguyên bảng | bảng nhỏ (< 20 dòng), cần so sánh chéo |
| **Group by** | gom theo cột chính rồi mô tả | bảng có nhóm rõ ràng |
| **Không index** | để cho SQL/code truy vấn | bảng > 500 dòng, dữ liệu số thuần |

### 1.3 Nguyên tắc quyết định — quan trọng nhất hôm nay

```
Bảng là DỮ LIỆU (danh sách khách hàng, giao dịch, lịch hẹn)
   → KHÔNG đưa vào RAG. Đưa vào database, truy vấn bằng SQL.

Bảng là TRI THỨC (bảng giá, ma trận chính sách, bảng quy đổi)
   → Đưa vào RAG dưới dạng câu có ngữ nghĩa.
```

> Sai lầm phổ biến: nhét 3.000 dòng khách hàng vào vector DB rồi hỏi "khách nào chi tiêu nhiều nhất". RAG **không thể** trả lời đúng — đó là câu hỏi tổng hợp, cần SQL. Nhớ lại Ngày 1.

### 1.4 Những cái bẫy của Excel

| Bẫy | Hệ quả |
|---|---|
| Ô gộp (merged cells) | giá trị chỉ nằm ở ô đầu, các ô sau rỗng |
| Nhiều sheet | quên sheet quan trọng |
| Header không ở dòng 1 | cột bị đặt tên sai |
| Công thức | đọc ra công thức thay vì giá trị (`data_only=True`) |
| Ngày tháng | Excel lưu dạng số serial |
| Ô ghi chú | chứa điều kiện quan trọng, dễ bỏ sót |

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| openpyxl | https://openpyxl.readthedocs.io/ |
| pandas read_excel | https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html |

---

## 3. Thực hành (80 phút)

`leanai_core/parsers/excel.py`:

```python
"""Parser Excel: bảng -> câu có ngữ nghĩa."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class SheetResult:
    name: str
    n_rows: int
    n_cols: int
    columns: list[str]
    texts: list[str] = field(default_factory=list)
    strategy: str = ""
    skipped_reason: str = ""


def _find_header_row(df_raw: pd.DataFrame, max_scan: int = 10) -> int:
    """Tìm dòng header thật: dòng có nhiều ô chữ nhất và ít ô rỗng nhất."""
    best, best_score = 0, -1
    for i in range(min(max_scan, len(df_raw))):
        row = df_raw.iloc[i]
        filled = row.notna().sum()
        texty = sum(1 for v in row if isinstance(v, str) and v.strip())
        score = filled + texty
        if score > best_score:
            best, best_score = i, score
    return best


def _fmt(v) -> str:
    if pd.isna(v):
        return ""
    if isinstance(v, (int, float)) and float(v).is_integer() and abs(v) >= 1000:
        return f"{int(v):,}".replace(",", ".")
    if isinstance(v, pd.Timestamp):
        return v.strftime("%d/%m/%Y")
    return str(v).strip()


def row_to_sentence(row: pd.Series, columns: list[str], key_col: str | None = None) -> str:
    key = _fmt(row[key_col]) if key_col and key_col in row else ""
    parts = []
    for c in columns:
        if c == key_col:
            continue
        v = _fmt(row.get(c))
        if v:
            parts.append(f"{c}: {v}")
    body = ", ".join(parts)
    return f"{key} — {body}." if key else body + "."


def parse_excel(path: str | Path, max_rows_for_rag: int = 500) -> list[SheetResult]:
    path = Path(path)
    xls = pd.ExcelFile(path)
    results: list[SheetResult] = []

    for sheet in xls.sheet_names:
        raw = pd.read_excel(path, sheet_name=sheet, header=None)
        if raw.empty:
            continue
        hdr = _find_header_row(raw)
        df = pd.read_excel(path, sheet_name=sheet, header=hdr)
        df = df.dropna(how="all").dropna(axis=1, how="all")
        df = df.ffill(axis=0) if df.isna().sum().sum() / max(df.size, 1) > 0.2 else df
        cols = [str(c).strip() for c in df.columns]
        df.columns = cols

        res = SheetResult(name=sheet, n_rows=len(df), n_cols=len(cols), columns=cols)

        if len(df) > max_rows_for_rag:
            res.skipped_reason = (f"{len(df)} dòng > {max_rows_for_rag} — đây là DỮ LIỆU, "
                                  "nên đưa vào database và truy vấn bằng SQL, không phải RAG")
            results.append(res)
            continue

        key_col = cols[0] if cols else None
        if len(df) <= 20:
            res.strategy = "markdown+rows"
            res.texts.append(f"Bảng '{sheet}':\n" + df.to_markdown(index=False))
        else:
            res.strategy = "rows"
        for _, row in df.iterrows():
            s = row_to_sentence(row, cols, key_col)
            if len(s) > 10:
                res.texts.append(f"[{sheet}] {s}")
        results.append(res)

    return results
```

`exercises/day40/excel_test.py`:

```python
from pathlib import Path
from leanai_core.parsers.excel import parse_excel

for f in sorted(Path("data/docs").glob("*.xlsx")):
    print(f"\n{'='*70}\n{f.name}")
    for s in parse_excel(f):
        print(f"\n  Sheet '{s.name}': {s.n_rows} dòng × {s.n_cols} cột")
        print(f"  Cột: {s.columns[:6]}")
        if s.skipped_reason:
            print(f"  ⏭ BỎ QUA: {s.skipped_reason}")
            continue
        print(f"  Chiến lược: {s.strategy} | {len(s.texts)} đoạn text")
        for t in s.texts[:3]:
            print(f"    • {t[:130]}")
```

---

## 4. Bài tập

**Bài 1 — Bảng giá thật.** Tạo/tìm một file bảng giá Excel có: nhiều sheet, ô gộp, header ở dòng 3, cột ghi chú. Chạy parser. Kiểm tra từng câu sinh ra có **đọc hiểu được độc lập** không (không cần nhìn bảng).

**Bài 2 — Đo chất lượng truy hồi.** Nạp bảng giá vào vector DB bằng 2 cách: (a) markdown table thô, (b) row-to-sentence. Chạy 10 truy vấn kiểu "gói trị liệu da giá bao nhiêu", "gói nào 10 buổi". So sánh recall@3. Ghi số liệu.

**Bài 3 — Ranh giới RAG vs SQL.** Viết `progress/notes/day40.md`: liệt kê 10 câu hỏi về dữ liệu spa, phân loại mỗi câu cần **RAG** hay **SQL**, giải thích. Ví dụ cần SQL: "tổng doanh thu tháng 8", "khách nào chi nhiều nhất", "bao nhiêu khách quá hạn".
*Đây chính là thiết kế bạn sẽ dùng ở Ngày 82.*

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 40 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Tự tìm được dòng header, không giả định dòng 1
- [ ] Row-to-sentence sinh câu đọc hiểu được độc lập
- [ ] Từ chối bảng > 500 dòng kèm lý do rõ ràng
- [ ] Xử lý được ô gộp và nhiều sheet
- [ ] Có số liệu so sánh 2 chiến lược chuyển bảng
- [ ] Phân loại được 10 câu hỏi RAG vs SQL
- [ ] Quiz ≥ 80%
