# NGÀY 13 — Hallucination

> Phase 1 · 25' lý thuyết — 15' tài liệu — 70' code — 10' note

## 🎯 Mục tiêu

Đo được tỉ lệ bịa của model trên 20 câu hỏi, và xây **bộ 6 kỹ thuật giảm bịa** mà bạn sẽ dùng suốt Phase 3–6.

---

## 1. Lý thuyết cốt lõi (25 phút)

### 1.1 Hallucination không phải lỗi — là bản chất

Model được train để sinh chuỗi token **có xác suất cao**, không phải chuỗi token **đúng sự thật**. Khi không biết, nó vẫn sinh ra thứ *trông giống* câu trả lời đúng, vì đó là mẫu văn bản phổ biến nhất trong dữ liệu train.

Cộng thêm RLHF (Ngày 12): "tôi không biết" bị chấm thấp → model học cách **luôn có câu trả lời**.

### 1.2 Bốn loại bịa — phân biệt để chữa đúng

| Loại | Ví dụ | Cách chữa |
|---|---|---|
| **Bịa sự thật** | "Spa mở cửa 8h–22h" (thực tế 9h–20h) | RAG + trích nguồn |
| **Bịa nguồn** | trích dẫn điều khoản/tài liệu không tồn tại | Bắt trả về ID chunk có thật, verify |
| **Bịa suy luận** | tính sai nhưng trình bày rất thuyết phục | Để code làm toán |
| **Bịa ngoài ngữ cảnh** | thêm thông tin không có trong tài liệu đã cho | Guardrail "chỉ dùng tài liệu được cấp" |

### 1.3 Khi nào model dễ bịa nhất

```
Nguy cơ cao ▲
            │ ● câu hỏi về dữ liệu riêng không được cung cấp
            │ ● câu hỏi rất cụ thể (số, ngày, tên riêng, mã số)
            │ ● câu hỏi về sự kiện sau knowledge cutoff
            │ ● câu hỏi có tiền giả định sai ("vì sao spa X phá sản?")
            │ ● chuỗi suy luận nhiều bước
            │ ● ngôn ngữ ít dữ liệu train
Nguy cơ thấp│ ● kiến thức phổ thông, có trong tài liệu được cấp
            ▼
```

### 1.4 Sáu kỹ thuật giảm bịa — thuộc lòng

```
1. CUNG CẤP NGỮ CẢNH   → RAG. Không có tài liệu thì model buộc phải đoán
2. CHO PHÉP NÓI KHÔNG  → "Nếu tài liệu không có, trả lời: KHÔNG ĐỦ THÔNG TIN"
3. BẮT TRÍCH NGUỒN     → mỗi khẳng định kèm chunk_id; không có nguồn = không được nói
4. GIỚI HẠN PHẠM VI    → "CHỈ dùng thông tin trong <documents>. Không dùng kiến thức nền"
5. TÁCH TÍNH TOÁN      → mọi phép tính do code làm, LLM chỉ diễn đạt
6. KIỂM TRA LẠI        → pass 2: "câu trả lời này có được tài liệu hỗ trợ không?"
```

Thêm: **temperature thấp** giúp một chút nhưng **không giải quyết** (Ngày 9 đã chứng minh).

### 1.5 Mức chấp nhận được cho sản phẩm

| Loại nội dung | Tỉ lệ bịa tối đa | Bắt buộc |
|---|---|---|
| Số liệu tiền bạc, liều lượng, ngày giờ | **0%** | code tính, không phải LLM |
| Trả lời từ tài liệu nội bộ | < 3% | có trích nguồn |
| Giải thích/tóm tắt | < 5% | có người duyệt nếu gửi ra ngoài |
| Nội dung sáng tạo (tin nhắn) | không áp dụng | nhưng **mọi con số trong tin nhắn phải từ DB** |

Trong CareDesk-AI: tin nhắn gửi khách chứa số buổi còn lại, ngày hết hạn → **những con số đó phải do code chèn vào template, không để LLM tự viết**. Đây là quyết định kiến trúc bạn sẽ thực thi ở Ngày 86.

---

## 2. Tài liệu (15 phút)

| Nguồn | Link | Bắt buộc |
|---|---|---|
| Anthropic — Reduce hallucinations | https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-hallucinations | ✅ |
| Survey of Hallucination in LLMs (abstract + taxonomy) | https://arxiv.org/abs/2311.05232 | ✅ |

---

## 3. Thực hành (70 phút)

`exercises/day13/hallucination_bench.py`:

```python
"""Ngày 13: đo tỉ lệ bịa và hiệu quả của từng kỹ thuật chống bịa."""
import os, json
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

# Tài liệu DUY NHẤT model được phép dùng
DOCS = """[DOC-1] Phòng khám Ánh Dương mở cửa 9h00-20h00 từ thứ 2 đến thứ 7, chủ nhật nghỉ.
[DOC-2] Gói Trị liệu da mặt: 10 buổi, giá 12.000.000đ, hạn sử dụng 6 tháng.
[DOC-3] Chính sách hoàn tiền: hoàn 80% giá trị số buổi chưa sử dụng, trừ phí xử lý 200.000đ.
[DOC-4] Khách có thể chuyển nhượng gói cho người thân, cần báo trước 3 ngày làm việc."""

# 20 câu: có đáp án trong tài liệu / KHÔNG có / có tiền giả định sai
QUESTIONS = [
    ("Phòng khám mở cửa lúc mấy giờ?", "answerable"),
    ("Chủ nhật có làm việc không?", "answerable"),
    ("Gói trị liệu da mặt bao nhiêu buổi?", "answerable"),
    ("Hạn sử dụng gói là bao lâu?", "answerable"),
    ("Chuyển nhượng gói cần báo trước mấy ngày?", "answerable"),
    ("Phí xử lý khi hoàn tiền là bao nhiêu?", "answerable"),
    ("Chi nhánh Quận 7 có bãi đỗ xe không?", "unanswerable"),
    ("Số điện thoại hotline là gì?", "unanswerable"),
    ("Bác sĩ trưởng khoa tên gì?", "unanswerable"),
    ("Gói massage giá bao nhiêu?", "unanswerable"),
    ("Có chương trình trả góp không?", "unanswerable"),
    ("Thời gian mỗi buổi trị liệu là bao lâu?", "unanswerable"),
    ("Vì sao phòng khám đóng cửa chi nhánh Quận 3 năm ngoái?", "false_premise"),
    ("Chính sách bảo hành 2 năm áp dụng thế nào?", "false_premise"),
    ("Khách VIP được giảm 30%, đúng không?", "false_premise"),
    ("Gói 10 buổi, khách dùng 6, hoàn được bao nhiêu tiền?", "calculation"),
    ("Gói 10 buổi, khách dùng 3, hoàn được bao nhiêu tiền?", "calculation"),
    ("Mua 2 gói thì tổng bao nhiêu?", "calculation"),
    ("Nếu tôi đến lúc 20h30 thứ 6 có được không?", "answerable"),
    ("Gói mua ngày 01/01 thì hết hạn ngày nào?", "answerable"),
]

PROMPTS = {
    "naive": "Trả lời câu hỏi của khách hàng.\n\n{docs}\n\nCâu hỏi: {q}",

    "scoped": ("CHỈ sử dụng thông tin trong TÀI LIỆU dưới đây. Tuyệt đối không dùng "
               "kiến thức bên ngoài.\n\n{docs}\n\nCâu hỏi: {q}"),

    "full": ("CHỈ sử dụng thông tin trong TÀI LIỆU dưới đây.\n"
             "Nếu tài liệu không chứa câu trả lời, bạn PHẢI trả lời đúng chuỗi: "
             "KHÔNG ĐỦ THÔNG TIN\n"
             "Nếu câu hỏi chứa giả định sai so với tài liệu, hãy chỉ ra giả định sai đó.\n"
             "Mỗi khẳng định phải kèm mã tài liệu, ví dụ [DOC-1].\n"
             "Không tự tính toán tiền bạc — nếu cần tính, nói rõ công thức và để hệ thống tính.\n\n"
             "{docs}\n\nCâu hỏi: {q}"),
}


def ask(strategy: str, q: str) -> str:
    r = client.messages.create(
        model=MODEL, max_tokens=250, temperature=0,
        messages=[{"role": "user",
                   "content": PROMPTS[strategy].format(docs=DOCS, q=q)}],
    )
    return r.content[0].text.strip()


def auto_flag(kind: str, answer: str) -> str:
    """Chấm tự động sơ bộ. Bạn VẪN phải đọc tay để xác nhận."""
    said_no = "KHÔNG ĐỦ THÔNG TIN" in answer.upper() or "không có thông tin" in answer.lower()
    if kind in ("unanswerable", "false_premise"):
        return "OK" if said_no or "không" in answer.lower()[:60] else "NGHI BỊA"
    return "OK" if not said_no else "TỪ CHỐI NHẦM"


if __name__ == "__main__":
    results = []
    for strategy in ("naive", "scoped", "full"):
        flags = {"OK": 0, "NGHI BỊA": 0, "TỪ CHỐI NHẦM": 0}
        print(f"\n{'='*72}\nCHIẾN LƯỢC: {strategy}\n{'='*72}")
        for q, kind in QUESTIONS:
            a = ask(strategy, q)
            f = auto_flag(kind, a)
            flags[f] += 1
            print(f"[{f:>12}] ({kind:>13}) {q}\n              -> {a[:110]}")
            results.append({"strategy": strategy, "q": q, "kind": kind,
                            "answer": a, "flag": f})
        n = len(QUESTIONS)
        print(f"\n  Tỉ lệ nghi bịa: {flags['NGHI BỊA']}/{n} = {flags['NGHI BỊA']/n:.0%}"
              f" | từ chối nhầm: {flags['TỪ CHỐI NHẦM']}/{n}")

    with open("exercises/day13/results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\nĐã lưu results.json — MỞ RA ĐỌC TAY, đừng tin hoàn toàn auto_flag.")
```

### Đọc tay bắt buộc (20 phút)

Mở `results.json`, chấm lại từng câu bằng mắt. Auto-flag chỉ là sàng lọc thô. Lập bảng cuối:

| Chiến lược | Bịa | Từ chối nhầm | Trả lời đúng |
|---|---|---|---|
| naive | | | |
| scoped | | | |
| full | | | |

---

## 4. Bài tập

**Bài 1 — Lỗ hổng tính toán.** Xem 3 câu `calculation`. Model tính đúng không? Viết hàm Python tính chính xác, rồi thiết kế lại luồng: LLM trích tham số → code tính → LLM diễn đạt kết quả. Chạy thử.

**Bài 2 — Bộ test tái sử dụng.** Chuyển 20 câu hỏi thành `templates/eval-dataset.json` với cấu trúc:
```json
{"id": "q001", "question": "...", "kind": "unanswerable", "expected": "KHÔNG ĐỦ THÔNG TIN", "must_cite": []}
```
Bạn sẽ dùng lại chính file này ở Ngày 50 và Ngày 66.

**Bài 3 — Quy tắc sản phẩm.** Viết `progress/notes/day13-anti-hallucination.md`: 6 kỹ thuật, mỗi kỹ thuật kèm (a) áp dụng ở đâu trong CareDesk-AI, (b) chi phí phải trả (token/latency/tỉ lệ từ chối nhầm tăng).

---

## 5. Quiz nhớ bài

```powershell
python quiz\quiz.py --day 13
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Chạy đủ 3 chiến lược × 20 câu, có bảng số liệu **đã đọc tay**
- [ ] Chứng minh được `full` giảm bịa so với `naive` bằng số
- [ ] Nhận ra được đánh đổi: giảm bịa → tăng từ chối nhầm
- [ ] Có `templates/eval-dataset.json`
- [ ] Thuộc 6 kỹ thuật chống bịa
- [ ] Quiz ≥ 80%
