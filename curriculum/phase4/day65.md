# NGÀY 65 — PROJECT #3: Research Agent

> Phase 4 · Cả ngày. **Project thứ 3 vào portfolio.**

## 🎯 Mục tiêu

Agent nhận một yêu cầu nghiên cứu mở, tự lập kế hoạch, tìm kiếm, trích xuất, chuẩn hoá, khử trùng, chấm điểm và xuất báo cáo có nguồn.

> **Ví dụ nhiệm vụ:** "Tìm 30 nhà cung cấp camera AI cho trang trại tại Việt Nam."

---

## 1. Đặc tả

```
python -m projects.p3_research_agent.research \
    --goal "Tìm 30 nhà cung cấp camera AI cho trang trại tại Việt Nam" \
    --target 30 --out reports/camera-ai-vn.md
```

### Luồng

```
Mục tiêu
  ↓ [1] LẬP KẾ HOẠCH   : chia thành truy vấn tìm kiếm cụ thể
  ↓ [2] TÌM KIẾM       : nhiều truy vấn, nhiều trang
  ↓ [3] TRÍCH XUẤT     : từ mỗi trang -> bản ghi có cấu trúc
  ↓ [4] CHUẨN HOÁ      : tên công ty, giá, đơn vị tiền
  ↓ [5] KHỬ TRÙNG      : cùng công ty khác tên/khác trang
  ↓ [6] PHÂN LOẠI      : phân khúc, loại sản phẩm
  ↓ [7] CHẤM ĐIỂM      : mức phù hợp với tiêu chí
  ↓ [8] BÁO CÁO        : bảng + nguồn + phần thiếu dữ liệu
```

### Đầu ra bắt buộc

| Công ty | Sản phẩm | Giá | Phân khúc | Điểm phù hợp | Nguồn (URL) | Độ tin cậy |
|---|---|---|---|---|---|---|

Kèm:
- Số bản ghi tìm được / mục tiêu
- Danh sách trường bị thiếu và **vì sao**
- Chi phí, thời gian, số lần gọi tool
- Những gì agent **không** xác minh được

---

## 2. Tool cần có

```python
web_search(query, num_results)      # API tìm kiếm, hoặc file dữ liệu mẫu offline
fetch_page(url)                     # tải + trích text (tái dùng parser Ngày 38)
extract_records(text, schema)       # LLM trích bản ghi có cấu trúc
normalize_company(name)             # chuẩn hoá tên công ty (code, không LLM)
dedupe(records)                     # khử trùng theo tên chuẩn hoá + domain
save_record(record)                 # lưu vào store
```

> **Nếu không có API tìm kiếm:** chuẩn bị 20 trang HTML đã tải sẵn trong `data/research/` và cho `web_search` tìm trong đó. Bài học kỹ thuật không đổi, và bạn không bị chặn bởi việc mua API.

---

## 3. Khung code

`projects/p3-research-agent/models.py`:

```python
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl


class Segment(str, Enum):
    ENTERPRISE = "enterprise"; SMB = "smb"; CONSUMER = "consumer"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    HIGH = "high"; MEDIUM = "medium"; LOW = "low"


class Vendor(BaseModel):
    company: str = Field(min_length=2)
    company_normalized: str = ""
    website: str = ""
    product: str = ""
    price_vnd: int | None = None
    price_note: str = ""
    segment: Segment = Segment.UNKNOWN
    target_use_case: str = ""
    evidence_quote: str = Field(default="", description="trích nguyên văn từ nguồn")
    source_url: str = ""
    confidence: Confidence = Confidence.LOW
    missing_fields: list[str] = Field(default_factory=list)
    fit_score: float = 0.0
```

`projects/p3-research-agent/research.py` (khung chính):

```python
"""Research Agent — Project #3."""
import argparse, json, re, time
from collections import defaultdict
from pathlib import Path

from leanai_core.llm import LLMClient
from leanai_core.logging import new_trace, trace, log_event
from leanai_core.jsonutil import safe_json_loads
from .models import Vendor, Segment, Confidence

llm = LLMClient()

EXTRACT_PROMPT = """<page url="{url}">
{text}
</page>

Trích thông tin về NHÀ CUNG CẤP sản phẩm liên quan đến: {goal}

QUY TẮC:
- CHỈ trích thông tin có thật trong <page>. Không suy đoán.
- Mỗi bản ghi phải có evidence_quote: trích NGUYÊN VĂN từ trang.
- Trường không tìm thấy: để trống và ghi vào missing_fields.
- Giá: chỉ lấy nếu ghi rõ bằng số. Không quy đổi, không ước lượng.
- Nếu trang không phải nhà cung cấp, trả về danh sách rỗng.

CHỈ JSON: {{"vendors":[{{"company":"","website":"","product":"","price_vnd":null,
"price_note":"","segment":"enterprise|smb|consumer|unknown","target_use_case":"",
"evidence_quote":"","confidence":"high|medium|low","missing_fields":[]}}]}}"""

SUFFIXES = ["công ty", "cổ phần", "tnhh", "co.,ltd", "ltd", "jsc", "corp",
            "company", "việt nam", "vietnam", "group", "một thành viên"]


def normalize_company(name: str) -> str:
    s = re.sub(r"[^\w\s]", " ", name.lower())
    for suf in SUFFIXES:
        s = s.replace(suf, " ")
    return re.sub(r"\s+", " ", s).strip()


def dedupe(vendors: list[Vendor]) -> tuple[list[Vendor], int]:
    seen: dict[str, Vendor] = {}
    merged = 0
    for v in vendors:
        key = v.company_normalized or normalize_company(v.company)
        if key in seen:
            merged += 1
            old = seen[key]
            # giữ bản ghi nhiều thông tin hơn
            if len(v.missing_fields) < len(old.missing_fields):
                v.source_url = f"{old.source_url}; {v.source_url}"
                seen[key] = v
            else:
                old.source_url = f"{old.source_url}; {v.source_url}"
        else:
            v.company_normalized = key
            seen[key] = v
    return list(seen.values()), merged


def score(v: Vendor, criteria: dict) -> float:
    s = 0.0
    if v.price_vnd:                         s += 0.25
    if v.segment != Segment.UNKNOWN:        s += 0.15
    if v.website:                           s += 0.15
    if v.evidence_quote:                    s += 0.20
    if v.confidence == Confidence.HIGH:     s += 0.15
    elif v.confidence == Confidence.MEDIUM: s += 0.08
    if criteria.get("keyword", "") and criteria["keyword"].lower() in \
            (v.product + v.target_use_case).lower():
        s += 0.10
    return round(min(s, 1.0), 2)


def extract_from_page(url: str, text: str, goal: str) -> list[Vendor]:
    r = llm.complete(EXTRACT_PROMPT.format(url=url, text=text[:6000], goal=goal),
                     temperature=0, max_tokens=1500, tag="extract")
    out = []
    for d in safe_json_loads(r.text, {"vendors": []}).get("vendors", []):
        try:
            v = Vendor(**{**d, "source_url": url})
            if v.evidence_quote and v.evidence_quote[:40].lower() not in text.lower():
                v.confidence = Confidence.LOW
                v.missing_fields.append("evidence_not_verified")
            v.company_normalized = normalize_company(v.company)
            out.append(v)
        except Exception as e:
            log_event("extract_invalid", url=url, error=str(e))
    return out


def report(vendors: list[Vendor], goal: str, stats: dict) -> str:
    L = [f"# Báo cáo nghiên cứu\n", f"**Mục tiêu:** {goal}\n",
         f"**Tìm được:** {len(vendors)}/{stats['target']} bản ghi  ·  "
         f"**Trang đã đọc:** {stats['pages']}  ·  **Trùng đã gộp:** {stats['merged']}\n",
         f"**Chi phí:** ${stats['cost']:.4f}  ·  **Thời gian:** {stats['seconds']:.0f}s\n",
         "\n| # | Công ty | Sản phẩm | Giá (VNĐ) | Phân khúc | Điểm | Tin cậy | Nguồn |",
         "|---|---|---|---|---|---|---|---|"]
    for i, v in enumerate(sorted(vendors, key=lambda x: -x.fit_score), 1):
        price = f"{v.price_vnd:,}" if v.price_vnd else (v.price_note or "—")
        L.append(f"| {i} | {v.company} | {v.product[:40]} | {price} | "
                 f"{v.segment.value} | {v.fit_score} | {v.confidence.value} | "
                 f"{v.source_url[:40]} |")

    miss = defaultdict(int)
    for v in vendors:
        for m in v.missing_fields:
            miss[m] += 1
    L.append("\n## Dữ liệu còn thiếu\n")
    for k, n in sorted(miss.items(), key=lambda x: -x[1]):
        L.append(f"- `{k}`: thiếu ở {n}/{len(vendors)} bản ghi")

    L.append("\n## Giới hạn của báo cáo này\n")
    L.append("- Thông tin lấy từ web công khai, chưa liên hệ xác minh với nhà cung cấp")
    L.append("- Giá có thể đã thay đổi hoặc chỉ là giá tham khảo")
    L.append(f"- {sum(1 for v in vendors if v.confidence == Confidence.LOW)} bản ghi "
             "có độ tin cậy THẤP, cần kiểm chứng trước khi dùng")
    return "\n".join(L)
```

---

## 4. Việc phải làm

1. Cài đủ 6 tool (hoặc dùng bộ trang HTML offline).
2. Chạy trên **3 nhiệm vụ khác nhau**, không chỉ camera AI.
3. Kiểm chứng tay **10 bản ghi ngẫu nhiên**: thông tin có đúng không, `evidence_quote` có thật trong trang không?
4. Ghi `EVAL.md`: precision (bao nhiêu / 10 bản ghi đúng), độ phủ, chi phí, thời gian, các lỗi gặp phải.

---

## 5. PASS/FAIL

- [ ] Agent tự lập kế hoạch, không cần bạn chỉ từng bước
- [ ] Đạt ≥ 70% mục tiêu số lượng bản ghi
- [ ] Mọi bản ghi có `source_url` và `evidence_quote` verify được
- [ ] Khử trùng hoạt động (cùng công ty ghi khác tên vẫn gộp)
- [ ] Báo cáo nêu rõ **dữ liệu thiếu** và **giới hạn**
- [ ] Kiểm chứng tay: ≥ 8/10 bản ghi chính xác
- [ ] Không crash khi trang lỗi / không tải được
- [ ] Log đủ để truy lại toàn bộ quá trình (Ngày 64)

---

## 6. Tổng kết Phase 4

```powershell
python quiz\quiz.py --day 65
python quiz\quiz.py --exam 51 65
git add . ; git commit -m "day 65: Research Agent - Phase 4 complete"
```

`progress/notes/phase4-review.md`:
```markdown
## Agent khác chatbot ở chỗ nào (bằng lời của tôi)
## 3 thứ khó nhất khi làm agent
## Độ tin cậy agent của tôi: __ bước, __% thành công
## Guardrail nào đã cứu tôi khỏi lỗi gì
## Chi phí Phase 4: $___
```

> **Nhìn trước Phase 5:** 10 ngày AI Engineering — eval, tracing, cost, latency, security, reliability. Đây là phần biến "chạy được trên máy tôi" thành "bán được cho doanh nghiệp".
