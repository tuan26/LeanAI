# NGÀY 53 — Tool schema design

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Viết ra **quy tắc thiết kế tool schema** của riêng bạn, kiểm chứng bằng thực nghiệm.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Schema tốt giảm lỗi ngay từ gốc

| Kỹ thuật | Tác dụng |
|---|---|
| `enum` cho giá trị cố định | model không bịa giá trị lạ |
| `default` cho tham số phụ | giảm lỗi thiếu tham số |
| `pattern` (regex) | ép định dạng mã, ngày |
| `minimum`/`maximum` | chặn giá trị vô lý |
| `required` tối thiểu | càng ít bắt buộc càng dễ gọi đúng |
| description **mỗi tham số** | model hiểu phải điền gì |

### 1.2 Bốn phần của description tốt

```
1. LÀM GÌ        : "Lấy hồ sơ đầy đủ của một khách hàng theo mã."
2. KHI NÀO DÙNG  : "Dùng khi cần biết số buổi còn lại, ngày hết hạn."
3. KHI NÀO KHÔNG : "KHÔNG dùng để tìm theo tên — dùng search_customers."
4. TRẢ VỀ GÌ     : "Trả về JSON gồm ten, buoi_con_lai, ngay_het_han, vang_mat_ngay."
```

Phần 3 và 4 hay bị bỏ qua nhưng cải thiện rõ nhất.

### 1.3 Thiết kế đầu ra của tool

```python
# ❌ tồi — model phải đoán
return "Khách Lan còn 4 buổi hết hạn tháng 10"

# ✅ tốt — có cấu trúc, có đơn vị, có trường lỗi
return {"ten": "Nguyễn Thị Lan", "buoi_con_lai": 4,
        "ngay_het_han": "2026-10-12", "con_lai_ngay": 25,
        "don_vi_tien": "VND", "gia_tri_chua_dung": 4_800_000}
```

Thêm `hint` khi lỗi: `{"error": "...", "hint": "hãy thử search_customers trước"}` — model tự sửa được.

### 1.4 Giới hạn kích thước đầu ra

Tool trả 5.000 dòng → nổ context, tốn tiền, model lạc. Luôn:
- phân trang (`limit`, `offset`),
- cắt bớt và báo rõ `"truncated": true, "total": 1200`,
- chỉ trả trường cần thiết.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| JSON Schema | https://json-schema.org/understanding-json-schema/ |
| Anthropic — Tool use | https://docs.anthropic.com/en/docs/build-with-claude/tool-use |

---

## 3. Thực hành (80 phút)

`exercises/day53/schema_ab.py`:

```python
"""Ngày 53: A/B test schema tồi vs schema tốt."""
import json
from anthropic import Anthropic
from leanai_core.config import cfg
from leanai_core.tools import ToolRegistry

client = Anthropic(api_key=cfg.ANTHROPIC_API_KEY)

BAD = ToolRegistry()
GOOD = ToolRegistry()

DB = {"C001": {"ten": "Nguyễn Thị Lan", "con": 4},
      "C002": {"ten": "Trần Văn Bình", "con": 20}}


@BAD.register("book", "đặt lịch",
              {"type": "object",
               "properties": {"c": {"type": "string"}, "d": {"type": "string"},
                              "t": {"type": "string"}, "s": {"type": "string"}},
               "required": ["c", "d", "t", "s"]})
def book_bad(c, d, t, s):
    return f"ok {c} {d} {t} {s}"


@GOOD.register("book_appointment",
  ("Đặt lịch hẹn mới cho khách hàng. "
   "DÙNG KHI: người dùng muốn tạo lịch hẹn mới và đã có mã khách. "
   "KHÔNG DÙNG KHI: chỉ muốn xem lịch (dùng get_appointments) hoặc đổi lịch "
   "(dùng reschedule_appointment). "
   "TRẢ VỀ: JSON gồm appointment_id, trang_thai, ngay, gio."),
  {"type": "object",
   "properties": {
     "customer_id": {"type": "string", "pattern": "^C\\d{3}$",
                     "description": "Mã khách, đúng dạng C001"},
     "ngay": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
              "description": "Ngày hẹn, định dạng YYYY-MM-DD"},
     "gio": {"type": "string", "pattern": "^\\d{2}:\\d{2}$",
             "description": "Giờ bắt đầu, 24h, ví dụ 14:00"},
     "dich_vu": {"type": "string",
                 "enum": ["tri_lieu_da", "massage", "cham_soc_da"],
                 "description": "Mã dịch vụ"},
     "ghi_chu": {"type": "string", "default": "",
                 "description": "Ghi chú tuỳ chọn cho lễ tân"}},
   "required": ["customer_id", "ngay", "gio", "dich_vu"]})
def book_good(customer_id, ngay, gio, dich_vu, ghi_chu=""):
    if customer_id not in DB:
        return {"error": f"không có khách {customer_id}",
                "hint": "dùng search_customers để lấy mã khách trước"}
    return {"appointment_id": "A99", "trang_thai": "confirmed",
            "customer_id": customer_id, "ngay": ngay, "gio": gio,
            "dich_vu": dich_vu, "ghi_chu": ghi_chu}


PROMPTS = [
 "Đặt lịch cho khách C001 ngày 25/09/2026 lúc 2 giờ chiều làm trị liệu da",
 "Đặt lịch massage cho C002 thứ 5 tuần sau 9h sáng",
 "Đặt lịch cho chị Lan ngày mai",                    # thiếu thông tin
]

for name, reg in (("SCHEMA TỒI", BAD), ("SCHEMA TỐT", GOOD)):
    print(f"\n{'='*70}\n{name}\n{'='*70}")
    for p in PROMPTS:
        r = client.messages.create(model=cfg.MODEL, max_tokens=600, temperature=0,
                                   tools=reg.api_tools(),
                                   messages=[{"role": "user", "content": p}])
        calls = [b for b in r.content if b.type == "tool_use"]
        txt = "".join(b.text for b in r.content if b.type == "text")
        print(f"\n> {p}")
        if calls:
            for b in calls:
                print(f"  gọi {b.name}({json.dumps(b.input, ensure_ascii=False)})")
                res = reg.execute(b.name, b.input)
                print(f"  -> {'OK ' + res.content[:90] if res.ok else 'LỖI ' + res.error}")
        else:
            print(f"  không gọi tool: {txt[:130]}")
```

**Chấm:** với schema tốt, model có tự hỏi lại khi thiếu thông tin không? Có chuyển "2 giờ chiều" thành `14:00` không? Có chuyển "25/09/2026" thành `2026-09-25` không?

---

## 4. Bài tập

**Bài 1 — Quy tắc của bạn.** Viết `templates/tool-schema-rules.md`: 10 quy tắc thiết kế tool, mỗi quy tắc kèm ví dụ ❌/✅ và **bằng chứng thực nghiệm** từ bài A/B hôm nay.

**Bài 2 — Phân trang.** Sửa `list_overdue_customers` thêm `limit`, `offset`, trả `{"items": [...], "total": N, "truncated": bool}`. Test với 200 khách giả — context có nổ không?

**Bài 3 — Hint tự sửa.** Với mỗi tool, thêm `hint` trong lỗi. Test: gọi sai → model có tự sửa ở lượt sau không? Đo tỉ lệ tự phục hồi.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 53 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Có `templates/tool-schema-rules.md` với 10 quy tắc + bằng chứng
- [ ] Schema tốt cho tỉ lệ gọi đúng cao hơn rõ rệt (có số)
- [ ] Tool có phân trang, không bao giờ trả về khối dữ liệu khổng lồ
- [ ] Lỗi tool có `hint` và model tự sửa được ≥ 70% ca
- [ ] Quiz ≥ 80%
