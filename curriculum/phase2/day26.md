# NGÀY 26 — Decomposition (chia nhỏ nhiệm vụ)

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Biến một prompt khổng lồ làm-mọi-thứ thành **pipeline nhiều bước** — chính xác hơn, debug được, rẻ hơn.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vì sao prompt "làm tất cả" luôn thất bại

```
❌ "Đọc hồ sơ khách, phát hiện cơ hội, ước tính giá trị, chọn kênh liên hệ,
    soạn tin nhắn, và đề xuất thời điểm gửi."
```

Vấn đề: một lỗi ở bước đầu lan sang mọi bước sau; bạn không biết bước nào hỏng; không đo được từng phần; không dùng lại được phần nào.

### 1.2 Pipeline: mỗi bước một việc

```
Hồ sơ khách
   ↓ [Bước 1: TRÍCH XUẤT]      T=0, output JSON    ← đo được: đúng trường?
   ↓ [Bước 2: PHÂN LOẠI]       T=0, output enum    ← đo được: đúng nhãn?
   ↓ [Bước 3: TÍNH TOÁN]       CODE, không LLM     ← chính xác 100%
   ↓ [Bước 4: GIẢI THÍCH]      T=0.3, văn xuôi     ← đo được: có dẫn chứng?
   ↓ [Bước 5: SOẠN TIN]        T=0.7, sáng tạo     ← đo được: qua Constraints?
Kết quả
```

Mỗi bước: temperature riêng, prompt riêng, test riêng, có thể đổi model riêng (bước đơn giản dùng model rẻ).

### 1.3 Ba kiểu chia nhỏ

| Kiểu | Khi nào | Ví dụ |
|---|---|---|
| **Tuần tự (chain)** | bước sau cần kết quả bước trước | trích xuất → phân loại → soạn tin |
| **Song song (map)** | các phần độc lập | phân tích 100 phản hồi cùng lúc |
| **Gộp (reduce)** | tổng hợp nhiều kết quả | 100 phản hồi → 5 chủ đề chính |

Map-reduce là cách xử lý tài liệu dài vượt context window — bạn sẽ dùng lại ở Phase 3.

### 1.4 Chain-of-thought — dùng có kiểm soát

Cho model "suy nghĩ trước khi trả lời" giúp cải thiện các bài toán nhiều bước:

```
<thinking>
(model lập luận ở đây)
</thinking>

<answer>
(câu trả lời cuối)
</answer>
```

Sau đó **code chỉ lấy phần `<answer>`**. Lợi: chính xác hơn. Hại: tốn token, chậm hơn. Chỉ dùng khi đo được cải thiện.

### 1.5 Đánh đổi

| | 1 prompt lớn | Pipeline |
|---|---|---|
| Số lần gọi API | 1 | 3–5 |
| Chi phí | thấp hơn? **không chắc** — prompt lớn cũng dài | thường tương đương |
| Latency | thấp hơn | cao hơn (trừ khi chạy song song) |
| Độ chính xác | thấp | **cao** |
| Debug | không thể | từng bước |
| Dùng lại | không | từng bước |

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Chain complex prompts | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/chain-prompts |
| Anthropic — Let Claude think (CoT) | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/chain-of-thought |

---

## 3. Thực hành (80 phút)

`exercises/day26/pipeline.py`:

```python
"""Ngày 26: 1 prompt khổng lồ vs pipeline 5 bước."""
import json, re
from leanai_core.llm import LLMClient
from leanai_core.jsonutil import safe_json_loads

llm = LLMClient()

PROFILE = """Khách hàng: Nguyễn Thị Lan, nữ, 42 tuổi, SĐT 0901234567.
Gói đang có: Trị liệu da mặt cao cấp, 10 buổi, giá 12.000.000đ, mua ngày 12/04/2026.
Đã dùng: 6 buổi. Lần cuối: 28/05/2026. Hạn dùng: 6 tháng kể từ ngày mua.
Lịch sử: khách từ 2024, tổng chi tiêu 38.000.000đ, mua 4 gói.
Ghi chú CRM: 03/2026 phàn nàn chờ 40 phút. Thích khung giờ sáng. Không thích bị gọi điện.
Hôm nay: 17/09/2026."""

# ---------- CÁCH A: một prompt làm tất cả ----------
MEGA = f"""{PROFILE}

Hãy phân tích khách hàng này: phát hiện cơ hội doanh thu, ước tính giá trị, đánh giá
độ tin cậy, chọn kênh liên hệ phù hợp, soạn tin nhắn, và đề xuất thời điểm gửi.
Trả về JSON."""

# ---------- CÁCH B: pipeline ----------
def step1_extract(profile: str) -> dict:
    r = llm.complete(
        f"<profile>{profile}</profile>\n\n"
        "Trích xuất thành JSON đúng schema sau, CHỈ JSON, không giải thích:\n"
        '{"ten":"","goi":"","gia_goi":0,"tong_buoi":0,"da_dung":0,"ngay_mua":"YYYY-MM-DD",'
        '"han_thang":0,"lan_cuoi":"YYYY-MM-DD","hom_nay":"YYYY-MM-DD",'
        '"kenh_khong_thich":[],"ghi_chu_quan_trong":[]}',
        temperature=0, max_tokens=500, tag="1-trích xuất")
    return safe_json_loads(r.text, {})


def step2_compute(d: dict) -> dict:
    """CODE làm toán — không để LLM tính (Ngày 1, Ngày 13)."""
    from datetime import date
    def parse(s): 
        y, m, dd = map(int, s.split("-")); return date(y, m, dd)
    mua, cuoi, nay = parse(d["ngay_mua"]), parse(d["lan_cuoi"]), parse(d["hom_nay"])
    het_han = date(mua.year + (mua.month + d["han_thang"] - 1) // 12,
                   (mua.month + d["han_thang"] - 1) % 12 + 1, mua.day)
    con_lai = d["tong_buoi"] - d["da_dung"]
    return {
        **d,
        "buoi_con_lai": con_lai,
        "ngay_ket_thuc": het_han.isoformat(),
        "ngay_con_lai": (het_han - nay).days,
        "ngay_vang_mat": (nay - cuoi).days,
        "gia_tri_chua_dung": round(d["gia_goi"] * con_lai / d["tong_buoi"]),
    }


def step3_classify(d: dict) -> dict:
    r = llm.complete(
        f"<data>{json.dumps(d, ensure_ascii=False)}</data>\n\n"
        "Phân loại cơ hội doanh thu. CHỈ JSON:\n"
        '{"loai":"GOI_CHUA_DUNG|QUA_HAN_TAI_KHAM|SAP_HET_HAN|KHACH_VIP_IM_LANG|KHONG_CO",'
        '"do_tin_cay":"CAO|TRUNG_BINH|THAP","rui_ro":["..."]}',
        temperature=0, max_tokens=300, tag="3-phân loại")
    return safe_json_loads(r.text, {})


def step4_explain(d: dict, cls: dict) -> str:
    r = llm.complete(
        f"<data>{json.dumps(d, ensure_ascii=False)}</data>\n"
        f"<classification>{json.dumps(cls, ensure_ascii=False)}</classification>\n\n"
        "Giải thích cho nhân viên CSKH vì sao đây là cơ hội, 3 gạch đầu dòng, "
        "mỗi ý ≤ 20 từ, mỗi ý phải dẫn một con số cụ thể từ <data>.",
        temperature=0.2, max_tokens=250, tag="4-giải thích")
    return r.text


def step5_message(d: dict, explain: str) -> str:
    r = llm.complete(
        f"<data>{json.dumps(d, ensure_ascii=False)}</data>\n<why>{explain}</why>\n\n"
        "Viết tin nhắn Zalo 2-3 câu. Xưng em, gọi chị + tên. Nêu 1 lý do cụ thể. "
        "Kết bằng câu hỏi về thời gian. Không dùng từ 'khuyến mãi'. "
        "Mọi con số phải lấy đúng từ <data>.",
        temperature=0.7, max_tokens=200, tag="5-soạn tin")
    return r.text


if __name__ == "__main__":
    print("="*70 + "\nCÁCH A — MỘT PROMPT LÀM TẤT CẢ\n" + "="*70)
    a = llm.complete(MEGA, temperature=0, max_tokens=1200, tag="mega prompt")
    print(a.text[:900])

    print("\n" + "="*70 + "\nCÁCH B — PIPELINE 5 BƯỚC\n" + "="*70)
    d = step1_extract(PROFILE)
    print(f"[1] trích xuất: {json.dumps(d, ensure_ascii=False)[:200]}")
    d = step2_compute(d)
    print(f"[2] tính (code): còn {d['buoi_con_lai']} buổi | hết hạn {d['ngay_ket_thuc']} "
          f"| còn {d['ngay_con_lai']} ngày | vắng {d['ngay_vang_mat']} ngày "
          f"| giá trị chưa dùng {d['gia_tri_chua_dung']:,}đ")
    cls = step3_classify(d)
    print(f"[3] phân loại: {cls}")
    ex = step4_explain(d, cls)
    print(f"[4] giải thích:\n{ex}")
    msg = step5_message(d, ex)
    print(f"[5] tin nhắn:\n{msg}")

    print("\n" + llm.usage.report())

    print("\n--- KIỂM TRA SỐ LIỆU ---")
    print("Đúng: còn 4 buổi, hết hạn 2026-10-12, vắng 112 ngày, giá trị chưa dùng 4.800.000đ")
    print("Cách A có đúng hết không? Cách B?")
```

---

## 4. Bài tập

**Bài 1 — So sánh chính xác.** Chạy cả 2 cách trên 5 hồ sơ khách khác nhau. Đếm số lỗi tính toán của mỗi cách. Dự đoán: cách A sẽ sai ít nhất 1 con số ở phần lớn hồ sơ.

**Bài 2 — Map-reduce.** Viết pipeline xử lý 50 phản hồi khách hàng: map (phân loại từng cái, chạy song song bằng `concurrent.futures`) → reduce (tổng hợp thành 5 chủ đề + ưu tiên). Đo latency khi chạy tuần tự vs song song.

**Bài 3 — CoT có đáng không.** Thêm `<thinking>` vào bước 3 (phân loại). Đo trên 20 case: độ chính xác tăng bao nhiêu, token tăng bao nhiêu, latency tăng bao nhiêu. Kết luận: dùng hay không?

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 26 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Pipeline 5 bước chạy được, mỗi bước có tag riêng trong usage report
- [ ] Bước tính toán do **code** làm, không phải LLM
- [ ] Chứng minh bằng số: pipeline chính xác hơn mega prompt
- [ ] Map-reduce chạy song song, có số liệu latency
- [ ] Quiz ≥ 80%
