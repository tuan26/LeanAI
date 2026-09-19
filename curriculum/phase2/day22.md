# NGÀY 22 — Zero-shot prompting

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Xây **bộ khung prompt zero-shot** và bộ 20 test case để đo. Từ hôm nay, mọi prompt đều phải đo được, không "cảm thấy tốt hơn".

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Zero-shot = không cho ví dụ

Chỉ mô tả nhiệm vụ. Rẻ nhất, nhanh nhất. **Luôn thử trước** few-shot (Ngày 23).

### 1.2 Sáu thành phần của prompt zero-shot tốt

```
1. NGỮ CẢNH   : ai đang hỏi, dùng để làm gì
2. NHIỆM VỤ   : động từ rõ ràng — phân loại, trích xuất, viết lại, tóm tắt
3. DỮ LIỆU    : bọc trong thẻ, tách khỏi chỉ dẫn
4. RÀNG BUỘC  : độ dài, giọng văn, điều cấm — phải ĐO ĐƯỢC
5. ĐỊNH DẠNG  : mô tả chính xác cấu trúc output
6. NGOẠI LỆ   : thiếu dữ liệu / không chắc thì làm gì
```

### 1.3 Ràng buộc mơ hồ vs đo được

| ❌ Mơ hồ | ✅ Đo được |
|---|---|
| "viết ngắn gọn" | "tối đa 50 từ" |
| "giọng thân thiện" | "xưng em, gọi khách chị/anh + tên" |
| "đừng bịa" | "chỉ dùng dữ liệu trong thẻ <data>; thiếu thì ghi KHÔNG CÓ" |
| "liệt kê vài ý" | "đúng 3 gạch đầu dòng" |

Nếu bạn không đo được ràng buộc bằng code, model cũng không biết mình có tuân thủ hay không.

### 1.4 Vị trí quan trọng

Nhắc lại Ngày 8: **yêu cầu định dạng đặt ở CUỐI**, ngay trước khi model sinh. Nhiều người viết định dạng ở đầu rồi dán 3000 token dữ liệu phía dưới — model quên mất.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Be clear and direct | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct |
| Anthropic — Use XML tags | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags |

---

## 3. Thực hành (80 phút)

`exercises/day22/zeroshot.py`:

```python
"""Ngày 22: prompt tồi vs prompt có cấu trúc, đo bằng code."""
from leanai_core.llm import LLMClient

llm = LLMClient()

FEEDBACK = [
 "Nhân viên nhiệt tình nhưng chờ hơi lâu, khoảng 40 phút mới tới lượt.",
 "Giá hơi cao so với chỗ khác, nhưng chất lượng ổn. Sẽ cân nhắc quay lại.",
 "Rất tệ! Đặt lịch 2h mà 3h mới được vào. Không ai xin lỗi.",
 "Da mình cải thiện rõ sau 5 buổi. Cảm ơn bác sĩ Hằng.",
 "Cơ sở vật chất sạch sẽ. Nhưng gửi xe khó, phải để ngoài đường.",
]

BAD = "Phân tích phản hồi khách hàng này:\n{fb}"

GOOD = """Bạn đang hỗ trợ quản lý vận hành chuỗi spa phân tích phản hồi khách hàng
để quyết định ưu tiên cải thiện.

NHIỆM VỤ: phân loại phản hồi dưới đây.

<feedback>
{fb}
</feedback>

RÀNG BUỘC:
- Cảm xúc: chọn đúng 1 trong: TÍCH_CỰC | TRUNG_LẬP | TIÊU_CỰC
- Chủ đề: chọn tối đa 2 trong: THỜI_GIAN_CHỜ | GIÁ | CHẤT_LƯỢNG | THÁI_ĐỘ | CƠ_SỞ_VẬT_CHẤT | KHÁC
- Mức khẩn: CAO nếu khách có dấu hiệu sẽ rời bỏ, TRUNG_BÌNH nếu phàn nàn nhưng còn thiện chí, THẤP nếu không
- Trích dẫn: đúng 1 đoạn nguyên văn ngắn từ phản hồi làm bằng chứng
- Nếu phản hồi không rõ nghĩa: ghi KHÔNG_RÕ ở mọi trường

ĐỊNH DẠNG (đúng 4 dòng, không thêm gì khác):
CẢM_XÚC: <giá trị>
CHỦ_ĐỀ: <giá trị, cách nhau bởi dấu phẩy>
KHẨN: <giá trị>
BẰNG_CHỨNG: "<trích dẫn>" """


def check(out: str, fb: str) -> list[str]:
    """Chấm tự động — đây mới là phần quan trọng."""
    errs = []
    lines = [l for l in out.strip().splitlines() if l.strip()]
    if len(lines) != 4:
        errs.append(f"số dòng = {len(lines)}, cần 4")
    keys = ["CẢM_XÚC:", "CHỦ_ĐỀ:", "KHẨN:", "BẰNG_CHỨNG:"]
    for i, k in enumerate(keys):
        if i < len(lines) and not lines[i].startswith(k):
            errs.append(f"dòng {i+1} không bắt đầu bằng {k}")
    if "CẢM_XÚC:" in out:
        v = out.split("CẢM_XÚC:")[1].split("\n")[0].strip()
        if v not in ("TÍCH_CỰC", "TRUNG_LẬP", "TIÊU_CỰC", "KHÔNG_RÕ"):
            errs.append(f"cảm xúc lạ: {v}")
    if '"' in out:
        q = out.split('BẰNG_CHỨNG:')[-1].strip().strip('"')
        if q and q not in fb:
            errs.append("bằng chứng không có trong phản hồi (bịa)")
    return errs


if __name__ == "__main__":
    for name, tpl in (("PROMPT TỒI", BAD), ("PROMPT CÓ CẤU TRÚC", GOOD)):
        print(f"\n{'='*70}\n{name}\n{'='*70}")
        total_err = 0
        for fb in FEEDBACK:
            r = llm.complete(tpl.format(fb=fb), max_tokens=200, tag=name)
            errs = check(r.text, fb)
            total_err += len(errs)
            print(f"\n{fb[:45]}...")
            print(f"  -> {r.text.strip()[:150].replace(chr(10), ' | ')}")
            if errs:
                print(f"  ❌ {errs}")
        print(f"\nTổng lỗi: {total_err}  |  tỉ lệ đạt: "
              f"{sum(1 for _ in FEEDBACK if True)} mẫu")
    print("\n" + llm.usage.report())
```

---

## 4. Bài tập

**Bài 1 — Bộ test 20 case.** Tạo `templates/prompt-testset.json`: 20 phản hồi khách hàng kèm nhãn đúng do **bạn tự gán**. Bao gồm 3 ca khó: phản hồi mỉa mai, phản hồi lẫn lộn khen-chê, phản hồi không liên quan.

**Bài 2 — Chạy và đo.** Chạy cả 2 prompt trên 20 case. Lập bảng:

| Prompt | Đúng định dạng | Đúng nhãn cảm xúc | Bịa bằng chứng | Token TB | Chi phí |
|---|---|---|---|---|---|

**Bài 3 — Thư viện prompt.** Tạo `templates/prompts/` với 3 prompt zero-shot hoàn chỉnh theo 6 thành phần: `classify_feedback`, `extract_customer_info`, `summarize_conversation`. Mỗi file kèm phần `## Test cases` và `## Kết quả đo`.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 22 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Prompt có cấu trúc đạt ≥ 90% đúng định dạng trên 20 case
- [ ] Có hàm `check()` chấm tự động, không chấm bằng mắt
- [ ] Có bảng so sánh 2 prompt bằng số
- [ ] `templates/prompt-testset.json` đủ 20 case có nhãn
- [ ] Quiz ≥ 80%
