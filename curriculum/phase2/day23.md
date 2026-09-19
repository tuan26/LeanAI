# NGÀY 23 — Few-shot prompting

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Đo **chính xác** few-shot cải thiện bao nhiêu so với zero-shot — và nó tốn thêm bao nhiêu token.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Few-shot dạy bằng ví dụ, không bằng mô tả

Một số thứ **không thể mô tả bằng lời** nhưng chỉ ra được bằng ví dụ: giọng văn thương hiệu, mức độ chi tiết, cách xử lý ca biên.

### 1.2 Quy tắc chọn ví dụ

| Quy tắc | Vì sao |
|---|---|
| **3–5 ví dụ** là điểm ngọt | thêm nữa lợi ích giảm, chi phí tăng tuyến tính |
| **Đa dạng**, không trùng dạng | model học mẫu, không học nội dung |
| **Có ít nhất 1 ca biên** | dạy cách xử lý ngoại lệ |
| **Ví dụ cuối gần nhất với ca thật** | ảnh hưởng mạnh nhất (recency) |
| **Định dạng giống hệt nhau** | model bắt chước cấu trúc rất mạnh |
| **Không có lỗi** | model sẽ sao chép cả lỗi của bạn |

### 1.3 Cạm bẫy

- **Thiên lệch nhãn:** nếu 4/5 ví dụ là TIÊU_CỰC, model sẽ thiên về TIÊU_CỰC. Cân bằng nhãn.
- **Thiên lệch độ dài:** ví dụ dài → output dài. Muốn output ngắn, ví dụ phải ngắn.
- **Sao chép nội dung:** model đôi khi bê nguyên chi tiết từ ví dụ vào output thật. Dùng dữ liệu ví dụ khác hẳn ca thật.

### 1.4 Khi nào few-shot xứng đáng

```
Chi phí thêm = (token ví dụ) × (số request)
Lợi ích      = tỉ lệ đúng tăng bao nhiêu điểm %
```

Nếu zero-shot đã đạt 95% → few-shot thường không đáng. Nếu zero-shot 70% và few-shot 92% → rất đáng. **Phải đo mới biết.**

### 1.5 Dynamic few-shot (nâng cao)

Thay vì 5 ví dụ cố định, chọn 5 ví dụ **giống ca hiện tại nhất** từ kho ví dụ (dùng embedding — Ngày 5). Đây là kỹ thuật mạnh, bạn sẽ quay lại sau Phase 3.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Multishot prompting | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/multishot-prompting |

---

## 3. Thực hành (80 phút)

`exercises/day23/fewshot.py`:

```python
"""Ngày 23: đo zero-shot vs few-shot trên cùng bộ test."""
import json
from pathlib import Path
from leanai_core.llm import LLMClient

llm = LLMClient()
TESTSET = json.loads(Path("templates/prompt-testset.json").read_text(encoding="utf-8"))

TASK = """Phân loại phản hồi khách hàng của spa.

RÀNG BUỘC:
- CẢM_XÚC: TÍCH_CỰC | TRUNG_LẬP | TIÊU_CỰC
- KHẨN: CAO | TRUNG_BÌNH | THẤP
ĐỊNH DẠNG: đúng 2 dòng
CẢM_XÚC: <giá trị>
KHẨN: <giá trị>"""

EXAMPLES = """Ví dụ:

<feedback>Chờ 40 phút mới tới lượt dù đã đặt hẹn. Lần thứ 3 rồi, chắc tôi đổi chỗ.</feedback>
CẢM_XÚC: TIÊU_CỰC
KHẨN: CAO

<feedback>Da cải thiện rõ sau liệu trình. Bác sĩ tư vấn kỹ.</feedback>
CẢM_XÚC: TÍCH_CỰC
KHẨN: THẤP

<feedback>Dịch vụ ổn, giá hơi cao. Chắc vẫn quay lại.</feedback>
CẢM_XÚC: TRUNG_LẬP
KHẨN: THẤP

<feedback>Hay quá, chờ 2 tiếng đồng hồ, dịch vụ 5 sao đấy.</feedback>
CẢM_XÚC: TIÊU_CỰC
KHẨN: TRUNG_BÌNH

<feedback>Cho hỏi mai có mở cửa không ạ?</feedback>
CẢM_XÚC: TRUNG_LẬP
KHẨN: THẤP"""


def parse(out: str) -> dict:
    d = {}
    for line in out.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip()
    return d


def run(mode: str) -> dict:
    ok_sent = ok_urg = ok_fmt = 0
    for case in TESTSET:
        prompt = (f"{TASK}\n\n{EXAMPLES}\n\nBây giờ phân loại:\n"
                  f"<feedback>{case['text']}</feedback>") if mode == "few" else \
                 (f"{TASK}\n\n<feedback>{case['text']}</feedback>")
        r = llm.complete(prompt, max_tokens=60, tag=mode)
        d = parse(r.text)
        if set(d) == {"CẢM_XÚC", "KHẨN"}:
            ok_fmt += 1
        ok_sent += d.get("CẢM_XÚC") == case["sentiment"]
        ok_urg += d.get("KHẨN") == case["urgency"]
    n = len(TESTSET)
    return {"đúng định dạng": f"{ok_fmt}/{n}",
            "đúng cảm xúc": f"{ok_sent}/{n} ({ok_sent/n:.0%})",
            "đúng mức khẩn": f"{ok_urg}/{n} ({ok_urg/n:.0%})"}


if __name__ == "__main__":
    for mode in ("zero", "few"):
        print(f"\n=== {mode.upper()}-SHOT ===")
        for k, v in run(mode).items():
            print(f"  {k:<18} {v}")
    print("\n" + llm.usage.report())
    print("\nCâu hỏi: mức cải thiện có xứng với token tăng thêm không?")
```

---

## 4. Bài tập

**Bài 1 — Đường cong số ví dụ.** Chạy với 0, 1, 3, 5, 8 ví dụ. Lập bảng `số ví dụ | độ chính xác | token/request | chi phí 1000 request`. Điểm ngọt nằm ở đâu?

**Bài 2 — Thiên lệch nhãn.** Tạo bộ ví dụ lệch (4/5 là TIÊU_CỰC) và bộ cân bằng. So sánh phân bố nhãn model dự đoán. Ghi lại mức lệch.

**Bài 3 — Few-shot cho tin nhắn.** Thu thập/viết 5 tin nhắn Zalo **do người thật viết** đúng giọng thương hiệu. Dùng làm few-shot cho `customer_message_writer`. So sánh với zero-shot: nhờ 3 người đọc mù (không biết cái nào là AI) chấm "cái nào nghe giống người thật hơn". Ghi kết quả.
*Đây là cách bạn diệt "mùi AI" trong CareDesk-AI.*

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 23 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Có số liệu zero-shot vs few-shot trên **cùng** 20 case
- [ ] Có đường cong theo số ví dụ, xác định được điểm ngọt
- [ ] Chứng minh được thiên lệch nhãn bằng số
- [ ] Kết luận rõ ràng: few-shot có đáng tiền cho tác vụ này không
- [ ] Quiz ≥ 80%
