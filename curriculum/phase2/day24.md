# NGÀY 24 — Role & context

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Hoàn thiện **thư viện system prompt** dùng suốt phần còn lại của chương trình, và biết vai trò nào thật sự có tác dụng, vai trò nào chỉ là mê tín.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vai trò có tác dụng — nhưng không phải kiểu bạn nghĩ

```
❌ "Bạn là một chuyên gia AI đẳng cấp thế giới với 30 năm kinh nghiệm"
   → gần như không cải thiện gì, chỉ tốn token

✅ "Bạn hỗ trợ nhân viên CSKH spa tại Việt Nam. Người đọc output của bạn là
    nhân viên 22-30 tuổi, không rành công nghệ, đang bận, cần quyết định trong 30 giây."
   → cải thiện thật, vì nó thay đổi ĐỘ DÀI, TỪ NGỮ, MỨC CHI TIẾT
```

**Quy tắc:** vai trò hữu ích khi nó nói rõ **ai đọc** và **để làm gì**, không phải khi nó tâng bốc model.

### 1.2 Bốn loại ngữ cảnh cần cung cấp

| Loại | Ví dụ |
|---|---|
| **Ngữ cảnh người đọc** | nhân viên bận, khách hàng 40+, sếp xem báo cáo |
| **Ngữ cảnh nghiệp vụ** | spa Việt Nam, khách quen xưng hô chị/em |
| **Ngữ cảnh hệ quả** | "output này sẽ được gửi thẳng cho khách" → cẩn trọng hơn |
| **Ngữ cảnh dữ liệu** | "dữ liệu lấy từ CRM, có thể thiếu trường" |

Ngữ cảnh hệ quả bị bỏ quên nhiều nhất, nhưng tác dụng mạnh nhất.

### 1.3 Cấu trúc system prompt chuẩn (chốt lại)

```
VAI TRÒ       : bạn là ai, làm cho ai, ai đọc output
NHIỆM VỤ      : động từ + đối tượng + mục đích
QUY TẮC       : 4-8 dòng, mỗi dòng đo được
ĐỊNH DẠNG     : chính xác cấu trúc
CẤM           : 3-5 điều tuyệt đối không
NGOẠI LỆ      : thiếu dữ liệu / không chắc / ngoài phạm vi
```

Giữ dưới **300 token**. Dài hơn thường là dấu hiệu bạn đang nhồi quy tắc mâu thuẫn nhau.

### 1.4 Quy tắc mâu thuẫn — lỗi phổ biến

```
"Viết thật chi tiết và đầy đủ"
"Tối đa 50 từ"
```

Model sẽ chọn một trong hai một cách ngẫu nhiên. Rà lại prompt của bạn, tìm mâu thuẫn — đây là nguyên nhân số 1 của output không ổn định.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — System prompts / role prompting | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/system-prompts |
| Anthropic — Prompt templates & variables | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompt-templates-and-variables |

---

## 3. Thực hành (80 phút)

### Phần A — Đo tác dụng của vai trò (30')

`exercises/day24/roles_ab.py`:

```python
"""Ngày 24: A/B test 4 kiểu system prompt trên cùng nhiệm vụ."""
from leanai_core.llm import LLMClient

llm = LLMClient()

CASE = """Khách: chị Lan, 42 tuổi. Gói trị liệu da mặt còn 4/10 buổi, hết hạn sau 25 ngày.
Lần cuối đến 112 ngày trước. Ghi chú CRM: từng phàn nàn chờ lâu (tháng 3).
Tổng chi tiêu 2 năm qua: 38 triệu."""

TASK = f"{CASE}\n\nNhân viên nên làm gì với khách này?"

VARIANTS = {
 "A. không vai trò": "",

 "B. vai trò tâng bốc": "Bạn là chuyên gia CSKH đẳng cấp thế giới với 30 năm kinh nghiệm, "
                        "được mệnh danh là bậc thầy giữ chân khách hàng.",

 "C. vai trò có ngữ cảnh người đọc":
   "Bạn hỗ trợ nhân viên CSKH của spa tại Việt Nam. Người đọc là nhân viên 22-30 tuổi, "
   "đang bận, cần quyết định trong 30 giây. Viết ngắn, đi thẳng vào hành động cụ thể.",

 "D. C + ngữ cảnh hệ quả":
   "Bạn hỗ trợ nhân viên CSKH của spa tại Việt Nam. Người đọc là nhân viên 22-30 tuổi, "
   "đang bận, cần quyết định trong 30 giây. Viết ngắn, đi thẳng vào hành động cụ thể.\n"
   "LƯU Ý: đề xuất của bạn sẽ dẫn đến việc nhắn tin cho khách thật. Khách đã từng phàn nàn "
   "có thể khó chịu nếu bị làm phiền sai cách. Nếu dữ liệu không đủ để chắc chắn, hãy nói rõ.",
}

for name, system in VARIANTS.items():
    r = llm.complete(TASK, system=system, max_tokens=300, temperature=0, tag=name)
    print(f"\n{'='*70}\n{name}  ({len(r.text.split())} từ, {r.output_tokens} token)\n{'='*70}")
    print(r.text)

print("\n" + llm.usage.report())
```

**Chấm:** phiên bản nào ngắn nhất? Phiên bản nào nêu được rủi ro khách từng phàn nàn? Phiên bản nào bạn thật sự dùng được?

### Phần B — Thư viện prompt (50')

Hoàn thiện `templates/system-prompts.md` với **5 prompt** đủ 6 phần, mỗi cái kèm 3 test case và kết quả đo:

| Prompt | Dùng ở |
|---|---|
| `customer_message_writer` | Ngày 86 |
| `opportunity_explainer` | Ngày 84 |
| `document_qa` | Ngày 48 |
| `requirement_analyst` | Ngày 30 (Project #1) |
| `data_extractor` | Ngày 29 |

---

## 4. Bài tập

**Bài 1 — Săn mâu thuẫn.** Lấy 3 prompt bạn đã viết từ Ngày 11 đến nay. Tìm mọi cặp quy tắc mâu thuẫn hoặc mơ hồ. Sửa lại. Ghi trước/sau.

**Bài 2 — Ngân sách token cho prompt.** Đo token của 5 prompt trong thư viện. Cái nào > 300 token → rút gọn ≥ 30% mà không mất quy tắc nào. Chứng minh bằng test rằng chất lượng không giảm.

**Bài 3 — Prompt cho người đọc khác nhau.** Viết 3 biến thể của `opportunity_explainer` cho 3 người đọc: nhân viên CSKH / quản lý phòng khám / chủ chuỗi. So sánh output. Ghi nhận xét: cùng dữ liệu, khác người đọc → khác gì?

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 24 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Chứng minh được vai trò tâng bốc **không** hiệu quả bằng hơn ngữ cảnh cụ thể
- [ ] `templates/system-prompts.md` có 5 prompt đủ 6 phần
- [ ] Mọi prompt ≤ 300 token
- [ ] Không còn quy tắc mâu thuẫn nào
- [ ] Quiz ≥ 80%
