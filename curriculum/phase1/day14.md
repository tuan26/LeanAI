# NGÀY 14 — MINI PROJECT: AI Explanation Engine

> Phase 1 · Cả ngày (2h ngày thường hoặc 4–6h cuối tuần). **Không học lý thuyết mới.**

## 🎯 Mục tiêu

Ghép toàn bộ Phase 1 thành một công cụ chạy được: đưa vào một văn bản khó (hợp đồng, điều khoản, quy trình), nhận về bản giải thích có cấu trúc cho người không chuyên.

Đây là sản phẩm **đầu tiên** vào portfolio của bạn.

---

## 1. Đặc tả

### Đầu vào
```
python explain.py --file samples/hop-dong-dich-vu.txt --audience "chủ spa không rành pháp lý"
```

### Đầu ra bắt buộc

```
════════════════════════════════════════════════════════
 TÓM TẮT
 <3-5 câu, người lớp 9 đọc hiểu>

 ĐIỀU KHOẢN QUAN TRỌNG
 1. <điều khoản> — <nghĩa là gì> — [trích dẫn nguyên văn]
 ...

 RỦI RO
 ⚠ <rủi ro> (mức: cao/trung bình/thấp) — <vì sao> — [trích dẫn]
 ...

 CÂU HỎI NÊN HỎI LẠI BÊN KIA
 - <câu hỏi>
 ...

 ĐỘ TIN CẬY: <cao/trung bình/thấp>
 Lý do: <vì sao, nêu rõ phần nào của tài liệu không rõ ràng>
 KHÔNG TÌM THẤY THÔNG TIN VỀ: <danh sách, nếu có>
════════════════════════════════════════════════════════
 Tokens: in=... out=...  |  Chi phí: $...  |  Thời gian: ...s
════════════════════════════════════════════════════════
```

### Yêu cầu kỹ thuật (mỗi cái map tới 1 ngày đã học)

| # | Yêu cầu | Từ ngày |
|---|---|---|
| 1 | Đếm token trước khi gửi, từ chối nếu vượt ngân sách | 4, 8 |
| 2 | Sắp xếp prompt đúng thứ tự: system → tài liệu → yêu cầu định dạng ở cuối | 8 |
| 3 | `temperature=0` (tác vụ trích xuất, không sáng tạo) | 9 |
| 4 | System prompt có vai trò, quy tắc, điều cấm | 11 |
| 5 | Prompt trung lập, không nịnh, được phép nói "tài liệu không nêu" | 12 |
| 6 | **Mọi khẳng định phải có trích dẫn nguyên văn từ tài liệu** | 13 |
| 7 | Có trường độ tin cậy + danh sách "không tìm thấy" | 13 |
| 8 | In ra token, chi phí, latency mỗi lần chạy | 4 |

---

## 2. Khung code

`projects/p0-explanation-engine/explain.py`:

```python
"""AI Explanation Engine — mini project Phase 1."""
import argparse, os, time
from pathlib import Path

import tiktoken
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
ENC = tiktoken.get_encoding("cl100k_base")

PRICE_IN, PRICE_OUT = 3.00, 15.00          # USD / 1M token — cập nhật theo bảng giá
MAX_INPUT_TOKENS = 12_000

SYSTEM = """Bạn là chuyên gia giải thích văn bản phức tạp cho người không có chuyên môn.

QUY TẮC BẮT BUỘC:
- CHỈ dùng thông tin có trong tài liệu được cung cấp. Không dùng kiến thức bên ngoài.
- Mỗi điều khoản và mỗi rủi ro PHẢI kèm trích dẫn nguyên văn đặt trong dấu ngoặc kép.
- Nếu tài liệu không đề cập một nội dung quan trọng, liệt kê vào mục KHÔNG TÌM THẤY.
- Không suy đoán ý định của bên soạn thảo.
- Không trấn an. Nếu có rủi ro, nói thẳng.
- Dùng ngôn ngữ đời thường. Mọi thuật ngữ chuyên ngành phải được giải thích ngay.
- Không tự tính toán con số. Nếu tài liệu có công thức, trình bày lại công thức.

ĐIỀU CẤM: không thêm lời chào, không thêm câu kết kiểu "hy vọng hữu ích"."""

TEMPLATE = """<document>
{doc}
</document>

Người đọc: {audience}

Hãy phân tích tài liệu trên theo ĐÚNG cấu trúc sau, không thêm mục nào khác:

## TÓM TẮT
(3-5 câu)

## ĐIỀU KHOẢN QUAN TRỌNG
(tối đa 7 mục, mỗi mục: tên điều khoản — nghĩa là gì — "trích dẫn nguyên văn")

## RỦI RO
(mỗi mục: mô tả — mức độ: cao/trung bình/thấp — vì sao — "trích dẫn nguyên văn")

## CÂU HỎI NÊN HỎI LẠI
(3-6 câu hỏi cụ thể)

## ĐỘ TIN CẬY
(cao/trung bình/thấp + lý do)

## KHÔNG TÌM THẤY THÔNG TIN VỀ
(danh sách, hoặc "không có")"""


def count(t: str) -> int:
    return len(ENC.encode(t))


def explain(doc: str, audience: str) -> dict:
    user = TEMPLATE.format(doc=doc, audience=audience)
    n_in = count(SYSTEM) + count(user)
    if n_in > MAX_INPUT_TOKENS:
        raise SystemExit(
            f"Tài liệu quá dài: {n_in} token > ngân sách {MAX_INPUT_TOKENS}.\n"
            f"Giải pháp: chia nhỏ tài liệu, hoặc chờ Phase 3 để dùng RAG."
        )

    t0 = time.time()
    r = client.messages.create(
        model=MODEL, max_tokens=2000, temperature=0,
        system=SYSTEM, messages=[{"role": "user", "content": user}],
    )
    dt = time.time() - t0
    text = r.content[0].text
    cost = (r.usage.input_tokens * PRICE_IN + r.usage.output_tokens * PRICE_OUT) / 1e6
    return {"text": text, "in": r.usage.input_tokens, "out": r.usage.output_tokens,
            "cost": cost, "sec": dt}


def verify_citations(doc: str, output: str) -> list[str]:
    """Kiểm tra mọi trích dẫn trong ngoặc kép có thật trong tài liệu không."""
    import re
    bad = []
    for quote in re.findall(r'"([^"]{15,})"', output):
        if quote.strip() not in doc:
            bad.append(quote[:60])
    return bad


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--file", required=True)
    p.add_argument("--audience", default="người không có chuyên môn")
    a = p.parse_args()

    doc = Path(a.file).read_text(encoding="utf-8")
    res = explain(doc, a.audience)

    print("=" * 70)
    print(res["text"])
    print("=" * 70)
    print(f"Tokens: in={res['in']} out={res['out']} | "
          f"Chi phí: ${res['cost']:.4f} (~{res['cost']*25000:.0f}đ) | "
          f"{res['sec']:.1f}s")

    bad = verify_citations(doc, res["text"])
    if bad:
        print(f"\n!! CẢNH BÁO: {len(bad)} trích dẫn KHÔNG có trong tài liệu (bịa nguồn):")
        for b in bad:
            print(f"   - {b}...")
    else:
        print("\n✓ Mọi trích dẫn đều có thật trong tài liệu")
```

---

## 3. Việc phải làm

### Bước 1 — Chuẩn bị 3 tài liệu test (30')

Tạo `projects/p0-explanation-engine/samples/`:
1. `hop-dong-dich-vu.txt` — hợp đồng dịch vụ spa (tự viết hoặc lấy mẫu công khai, ~2 trang)
2. `dieu-khoan-goi.txt` — điều khoản gói liệu trình có bẫy (phí ẩn, điều kiện hoàn tiền ngặt)
3. `quy-trinh-khieu-nai.txt` — quy trình nội bộ, viết lộn xộn, có mâu thuẫn

Tài liệu số 3 **phải có mâu thuẫn cố ý** — để xem engine có phát hiện không.

### Bước 2 — Chạy và sửa (60')

Chạy trên cả 3 tài liệu. Với mỗi lần chạy, ghi vào `projects/p0-explanation-engine/EVAL.md`:

| Tài liệu | Có đủ 6 mục? | Trích dẫn thật? | Bắt được mâu thuẫn? | Token | Chi phí | Giây |
|---|---|---|---|---|---|---|

### Bước 3 — Cải tiến (30')

Chọn **một** điểm yếu lớn nhất và sửa prompt. Đo lại. Ghi rõ: sửa gì, kết quả thay đổi thế nào.

Đây là vòng lặp cốt lõi của AI engineering: **đo → sửa → đo lại**. Bạn sẽ lặp nó 76 ngày nữa.

---

## 4. Tiêu chí PASS/FAIL

**PASS khi đủ 7 điều:**

- [ ] Chạy được bằng 1 lệnh trên file bất kỳ
- [ ] Output đủ 6 mục, đúng thứ tự
- [ ] `verify_citations` không báo trích dẫn bịa trên cả 3 tài liệu
- [ ] Từ chối đúng cách khi tài liệu vượt ngân sách token
- [ ] In được token / chi phí / latency
- [ ] Phát hiện được mâu thuẫn trong tài liệu số 3
- [ ] Có `EVAL.md` với số liệu 3 lần chạy + 1 lần cải tiến

**Mở rộng (làm nếu còn thời gian):**
- [ ] `--format json` trả về JSON đúng schema (bắc cầu sang Ngày 29–30)
- [ ] Xử lý file PDF (bắc cầu sang Ngày 38)
- [ ] So sánh 2 model khác nhau về chất lượng và chi phí

---

## 5. Tổng kết Phase 1

```powershell
python quiz\quiz.py --exam 1 14
python quiz\quiz.py --stats
```

Yêu cầu: **≥ 85%**. Dưới mức đó → dành cuối tuần ôn lại trước khi vào Phase 2.

### Viết tổng kết `progress/notes/phase1-review.md`

```markdown
## 3 điều quan trọng nhất tôi học được ở Phase 1
## 3 điều tôi tưởng mình hiểu nhưng thật ra không
## Số liệu tôi tự đo được (bảng tổng hợp từ Ngày 7 + bổ sung Ngày 8-13)
## Điều tôi sẽ làm khác đi ở Phase 2
## Tổng chi phí API Phase 1: $___
```

### Commit

```powershell
git add . ; git commit -m "day 14: AI Explanation Engine - Phase 1 complete"
```

---

## 6. Nhìn trước Phase 2

Từ Ngày 15, bạn chuyển từ *hiểu* sang *xây*. 16 ngày tới:
- Ngày 15–21: API, streaming, error handling → **chatbot hoàn chỉnh**
- Ngày 22–28: prompt engineering có hệ thống + phòng thủ injection
- Ngày 29–30: structured output → **AI Business Analyst** (Project #1)

Chuẩn bị trước: đảm bảo `pip install anthropic pydantic` đã xong.
