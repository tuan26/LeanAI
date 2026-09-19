# NGÀY 52 — Tool calling nhiều tool

> Phase 4 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

LLM tự chọn đúng tool trong bộ nhiều tool, và biết **giới hạn số tool** trước khi nó chọn sai.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Càng nhiều tool càng dễ sai

| Số tool | Độ chính xác chọn tool (kinh nghiệm) |
|---|---|
| 1–5 | rất cao |
| 6–12 | tốt |
| 13–25 | bắt đầu nhầm giữa tool giống nhau |
| > 25 | giảm rõ rệt, cần chia nhóm |

**Giải pháp khi nhiều tool:** phân tầng — một agent điều phối chọn *nhóm*, agent con có tool của nhóm đó. Hoặc dùng RAG trên chính mô tả tool.

### 1.2 Bốn nguyên nhân chọn sai tool

```
1. Mô tả chồng lấn   : get_customer vs find_customer vs lookup_client
2. Mô tả quá ngắn    : "lấy dữ liệu khách"
3. Thiếu ràng buộc âm: không nói rõ KHI NÀO KHÔNG dùng
4. Tên khó hiểu      : proc_cust_dat()
```

### 1.3 Song song vs tuần tự

Model có thể đề nghị **nhiều tool call trong một lượt** khi chúng độc lập:

```
get_customer("C001") ─┐
                      ├─► chạy song song → nhanh hơn nhiều
get_customer("C002") ─┘
```

Nhưng khi tool sau cần kết quả tool trước thì phải tuần tự. Code của bạn phải xử lý được cả hai.

### 1.4 Nguyên tắc thiết kế bộ tool

| Nguyên tắc | Ví dụ |
|---|---|
| Mỗi tool một việc rõ ràng | ❌ `manage_customer(action=...)` ✅ `get_customer` + `update_customer` |
| Tên động từ + danh từ | `get_appointments`, `send_message` |
| Tách read và write | read tự do; write cần duyệt (Ngày 61) |
| Trả về JSON có cấu trúc | không trả văn xuôi cho model tự hiểu |
| Có trường lỗi rõ ràng | `{"error": "...", "hint": "..."}` |

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Tool use best practices | https://docs.anthropic.com/en/docs/build-with-claude/tool-use |
| Anthropic — Parallel tool use | https://docs.anthropic.com/en/docs/build-with-claude/tool-use/implement-tool-use |

---

## 3. Thực hành (80 phút)

`exercises/day52/toolset.py` — bộ 8 tool cho CareDesk-AI:

```python
"""Bộ tool đầy đủ cho domain phòng khám."""
from datetime import date, datetime, timedelta

from leanai_core.tools import ToolRegistry

registry = ToolRegistry()

CUSTOMERS = {
 "C001": {"ten": "Nguyễn Thị Lan", "sdt": "0901234567", "goi": "Trị liệu da mặt",
          "tong": 10, "da_dung": 6, "gia": 12_000_000, "mua": "2026-04-12",
          "han_thang": 6, "lan_cuoi": "2026-05-28", "ghi_chu": "phàn nàn chờ lâu 03/2026"},
 "C002": {"ten": "Trần Văn Bình", "sdt": "0987654321", "goi": "Massage",
          "tong": 20, "da_dung": 0, "gia": 8_000_000, "mua": "2026-09-01",
          "han_thang": 12, "lan_cuoi": "2026-09-10", "ghi_chu": ""},
 "C003": {"ten": "Lê Thị Hoa", "sdt": "0912345678", "goi": "Chăm sóc da",
          "tong": 8, "da_dung": 8, "gia": 6_000_000, "mua": "2025-11-20",
          "han_thang": 6, "lan_cuoi": "2026-03-15", "ghi_chu": "khách VIP"},
}

APPOINTMENTS = [
 {"id": "A1", "customer_id": "C002", "ngay": "2026-09-20", "gio": "09:00", "trang_thai": "confirmed"},
 {"id": "A2", "customer_id": "C001", "ngay": "2026-09-21", "gio": "14:00", "trang_thai": "pending"},
]

SENT_LOG = []


def _derive(cid: str) -> dict:
    c = CUSTOMERS[cid]
    mua = datetime.strptime(c["mua"], "%Y-%m-%d").date()
    het = mua + timedelta(days=30 * c["han_thang"])
    cuoi = datetime.strptime(c["lan_cuoi"], "%Y-%m-%d").date()
    today = date.today()
    return {**c, "customer_id": cid,
            "buoi_con_lai": c["tong"] - c["da_dung"],
            "ngay_het_han": het.isoformat(),
            "con_lai_ngay": (het - today).days,
            "vang_mat_ngay": (today - cuoi).days,
            "gia_tri_chua_dung": round(c["gia"] * (c["tong"] - c["da_dung"]) / c["tong"])}


@registry.register("get_customer",
    "Lấy hồ sơ đầy đủ của MỘT khách hàng theo mã (dạng C001), gồm gói dịch vụ, "
    "số buổi còn lại, ngày hết hạn, số ngày vắng mặt, giá trị chưa dùng. "
    "KHÔNG dùng để tìm theo tên — dùng search_customers cho việc đó.",
    {"type": "object", "properties": {"customer_id": {"type": "string"}},
     "required": ["customer_id"]})
def get_customer(customer_id: str) -> dict:
    cid = customer_id.upper()
    if cid not in CUSTOMERS:
        return {"error": f"không có khách {cid}", "hint": "dùng search_customers để tìm theo tên"}
    return _derive(cid)


@registry.register("search_customers",
    "Tìm khách hàng theo TÊN hoặc số điện thoại (khớp một phần). Trả về danh sách "
    "mã khách và tên. Dùng khi người dùng nhắc tên khách thay vì mã.",
    {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})
def search_customers(query: str) -> list:
    q = query.lower()
    return [{"customer_id": k, "ten": v["ten"], "sdt": v["sdt"]}
            for k, v in CUSTOMERS.items() if q in v["ten"].lower() or q in v["sdt"]]


@registry.register("list_overdue_customers",
    "Liệt kê khách QUÁ HẠN tái khám: vắng mặt quá số ngày cho trước VÀ còn buổi chưa dùng. "
    "Dùng khi cần tìm cơ hội doanh thu, không dùng cho một khách cụ thể.",
    {"type": "object", "properties": {"min_days_absent": {"type": "integer", "default": 90}},
     "required": []})
def list_overdue_customers(min_days_absent: int = 90) -> list:
    out = []
    for cid in CUSTOMERS:
        d = _derive(cid)
        if d["vang_mat_ngay"] >= min_days_absent and d["buoi_con_lai"] > 0:
            out.append({k: d[k] for k in ("customer_id", "ten", "vang_mat_ngay",
                                          "buoi_con_lai", "gia_tri_chua_dung")})
    return sorted(out, key=lambda x: -x["gia_tri_chua_dung"])


@registry.register("get_appointments",
    "Lấy danh sách lịch hẹn theo ngày (YYYY-MM-DD) hoặc theo mã khách. "
    "Ít nhất một trong hai tham số phải có.",
    {"type": "object", "properties": {"ngay": {"type": "string"},
                                      "customer_id": {"type": "string"}}, "required": []})
def get_appointments(ngay: str = "", customer_id: str = "") -> list:
    if not ngay and not customer_id:
        return {"error": "cần ít nhất 'ngay' hoặc 'customer_id'"}
    return [a for a in APPOINTMENTS
            if (not ngay or a["ngay"] == ngay)
            and (not customer_id or a["customer_id"] == customer_id.upper())]


@registry.register("calculate_refund",
    "Tính số tiền hoàn cho khách theo chính sách: hoàn 80% giá trị buổi chưa dùng, "
    "trừ phí xử lý 200.000đ. LUÔN dùng tool này để tính tiền, không tự tính.",
    {"type": "object", "properties": {"customer_id": {"type": "string"}},
     "required": ["customer_id"]})
def calculate_refund(customer_id: str) -> dict:
    cid = customer_id.upper()
    if cid not in CUSTOMERS:
        return {"error": f"không có khách {cid}"}
    d = _derive(cid)
    gross = d["gia_tri_chua_dung"] * 0.8
    net = max(0, round(gross - 200_000))
    return {"gia_tri_chua_dung": d["gia_tri_chua_dung"], "ty_le_hoan": 0.8,
            "phi_xu_ly": 200_000, "so_tien_hoan": net,
            "cong_thuc": "giá_trị_chưa_dùng × 0.8 − 200.000"}


@registry.register("send_message",
    "GỬI tin nhắn Zalo/SMS thật cho khách hàng. ĐÂY LÀ HÀNH ĐỘNG KHÔNG THỂ HOÀN TÁC. "
    "Chỉ gọi khi người dùng đã xác nhận rõ ràng muốn gửi.",
    {"type": "object", "properties": {"customer_id": {"type": "string"},
                                      "channel": {"type": "string", "enum": ["zalo", "sms"]},
                                      "message": {"type": "string"}},
     "required": ["customer_id", "channel", "message"]},
    requires_approval=True, read_only=False)
def send_message(customer_id: str, channel: str, message: str) -> dict:
    SENT_LOG.append({"customer_id": customer_id, "channel": channel,
                     "message": message, "at": datetime.now().isoformat()})
    return {"status": "sent", "to": CUSTOMERS[customer_id.upper()]["sdt"],
            "channel": channel, "length": len(message)}
```

`exercises/day52/multi_tool.py`:

```python
"""Ngày 52: đo khả năng chọn đúng tool."""
import json
from anthropic import Anthropic
from leanai_core.config import cfg
from exercises.day52.toolset import registry

client = Anthropic(api_key=cfg.ANTHROPIC_API_KEY)

CASES = [
 ("Khách C001 còn mấy buổi?", ["get_customer"]),
 ("Tìm khách tên Lan", ["search_customers"]),
 ("Có khách nào lâu không quay lại không?", ["list_overdue_customers"]),
 ("Nếu chị Lan huỷ gói thì hoàn bao nhiêu tiền?", ["search_customers", "calculate_refund"]),
 ("Mai có lịch hẹn nào không?", ["get_appointments"]),
 ("So sánh C001 và C002", ["get_customer"]),
]

def run(q: str, max_turns: int = 6):
    messages = [{"role": "user", "content": q}]
    used = []
    for _ in range(max_turns):
        r = client.messages.create(model=cfg.MODEL, max_tokens=1200, temperature=0,
                                   tools=registry.api_tools(), messages=messages)
        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text"), used
        messages.append({"role": "assistant", "content": r.content})
        results = []
        for b in r.content:
            if b.type != "tool_use":
                continue
            used.append(b.name)
            res = registry.execute(b.name, b.input)
            results.append({"type": "tool_result", "tool_use_id": b.id,
                            "content": res.content if res.ok else f"Lỗi: {res.error}",
                            "is_error": not res.ok})
        messages.append({"role": "user", "content": results})
    return "[hết lượt]", used


correct = 0
for q, expected in CASES:
    ans, used = run(q)
    ok = all(e in used for e in expected)
    correct += ok
    print(f"\n{'✓' if ok else '✗'} {q}")
    print(f"   tool dùng: {used} | mong đợi: {expected}")
    print(f"   {ans[:130]}")

print(f"\nChọn đúng tool: {correct}/{len(CASES)}")
print(f"Tổng lần gọi tool: {len(registry.calls)}")
```

---

## 4. Bài tập

**Bài 1 — Đo giới hạn.** Nhân bản tool thành 5, 10, 20, 30 tool (thêm tool giả gần giống nhau). Đo độ chính xác chọn tool ở mỗi mức. Vẽ bảng. Ngưỡng nào bắt đầu hỏng?

**Bài 2 — Tool chồng lấn.** Tạo 3 tool mô tả gần giống nhau. Đo tỉ lệ nhầm. Sửa description thêm ràng buộc âm ("KHÔNG dùng khi..."). Đo lại.

**Bài 3 — Song song.** Hỏi "so sánh C001, C002, C003". Model có gọi 3 tool trong 1 lượt không? Đo latency khi chạy song song vs tuần tự bằng `ThreadPoolExecutor`.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 52 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Bộ 6+ tool hoạt động, model tự chọn đúng ≥ 5/6 ca
- [ ] Tool `calculate_refund` được dùng thay vì model tự tính
- [ ] Có bảng đo độ chính xác theo số lượng tool
- [ ] Sửa được lỗi chọn nhầm bằng ràng buộc âm trong description
- [ ] Quiz ≥ 80%
