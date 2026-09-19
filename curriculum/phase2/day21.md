# NGÀY 21 — Mini chatbot (tổng hợp tuần 3)

> Phase 2 · Cả buổi. Ghép Ngày 15–20 thành một sản phẩm chạy được.

## 🎯 Mục tiêu

Một CLI chatbot **đủ chất lượng production nhỏ**: có bộ nhớ, stream, chịu lỗi, đếm tiền, ghi log, và có lệnh điều khiển.

---

## 1. Đặc tả

```
$ python -m projects.p0_chatbot.chat --persona spa

╔═══════════════════════════════════════════════════════════╗
║  CareDesk Assistant — gõ /help để xem lệnh                ║
╚═══════════════════════════════════════════════════════════╝

Bạn: gói của chị Lan còn mấy buổi?
Bot: (stream từng chữ...)

[in=412 out=86 | $0.0019 | TTFT 0.7s | tổng phiên $0.0074]

Bạn: /stats
  Lượt: 5 | Token lịch sử: 1.240 | Chi phí phiên: $0.0074 (185đ)
  Theo tag: chat $0.0061 | nén hội thoại $0.0013

Bạn: /save
  Đã lưu conversations/2026-09-17-1432.json
```

### Lệnh bắt buộc

| Lệnh | Tác dụng |
|---|---|
| `/help` | danh sách lệnh |
| `/stats` | token, chi phí, số lượt |
| `/system` | xem system prompt đang dùng |
| `/facts` | xem dữ liệu cứng đang giữ |
| `/temp 0.7` | đổi temperature giữa chừng |
| `/save`, `/load <file>` | lưu / nạp hội thoại |
| `/clear` | xoá lịch sử, giữ facts |
| `/quit` | thoát, in báo cáo tổng |

### Yêu cầu kỹ thuật

| # | Yêu cầu | Từ ngày |
|---|---|---|
| 1 | Dùng `LLMClient` chung, không gọi SDK trực tiếp | 16 |
| 2 | System prompt đủ 5 phần | 17 |
| 3 | Dữ liệu cứng nằm trong facts, không trong lịch sử | 18 |
| 4 | Tự nén lịch sử khi vượt ngưỡng | 18 |
| 5 | Streaming + hiển thị TTFT | 19 |
| 6 | Retry + fallback khi API lỗi | 20 |
| 7 | Ghi log JSONL mọi lượt | 15 |
| 8 | In chi phí sau mỗi lượt và tổng khi thoát | 16 |

---

## 2. Khung code

`projects/p0-chatbot/chat.py`:

```python
"""CareDesk Assistant — CLI chatbot tổng hợp tuần 3."""
import argparse, json, sys
from datetime import datetime
from pathlib import Path

from leanai_core.llm import LLMClient
from leanai_core.memory import Conversation
from leanai_core.resilience import with_retry, with_fallback

PERSONAS = {
    "spa": """VAI TRÒ: Bạn là trợ lý ảo của chuỗi spa cao cấp tại Việt Nam, hỗ trợ NHÂN VIÊN
chăm sóc khách hàng (không nói chuyện trực tiếp với khách).

NHIỆM VỤ: trả lời câu hỏi về khách hàng, gói dịch vụ, lịch hẹn; gợi ý hành động tiếp theo.

QUY TẮC:
- Trả lời tối đa 80 từ, đi thẳng vào việc
- Mọi con số phải lấy từ mục THÔNG TIN XÁC THỰC, không được tự tính
- Khi gợi ý hành động, nêu rõ lý do dựa trên dữ liệu

CẤM: bịa số liệu; hứa thay khách hàng; dùng lời chào dài dòng.

THIẾU DỮ LIỆU: nói rõ "Tôi không có thông tin này trong hệ thống" và đề xuất cần tra cứu gì.""",

    "analyst": """VAI TRÒ: chuyên gia phân tích nghiệp vụ.
NHIỆM VỤ: bóc tách yêu cầu thành actor, use case, business rule, edge case.
QUY TẮC: dùng gạch đầu dòng; mỗi ý ≤ 15 từ; luôn nêu câu hỏi cần làm rõ.
CẤM: giả định thay khách hàng.
THIẾU DỮ LIỆU: liệt kê vào mục "CẦN LÀM RÕ".""",
}

HELP = """
  /help            danh sách lệnh
  /stats           token, chi phí, số lượt
  /system          xem system prompt
  /facts           xem dữ liệu cứng
  /fact k=v        thêm dữ liệu cứng
  /temp 0.7        đổi temperature
  /save            lưu hội thoại
  /load <file>     nạp hội thoại
  /clear           xoá lịch sử (giữ facts)
  /quit            thoát
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", default="spa", choices=list(PERSONAS))
    ap.add_argument("--temp", type=float, default=0.3)
    args = ap.parse_args()

    llm = LLMClient()
    conv = Conversation(llm, system=PERSONAS[args.persona], max_history_tokens=1500)
    # Dữ liệu cứng mẫu — thật ra sẽ đến từ database ở Phase 6
    conv.set_fact("Khách hàng", "Nguyễn Thị Lan (0901234567)")
    conv.set_fact("Gói", "Trị liệu da mặt 10 buổi — đã dùng 6, còn 4")
    conv.set_fact("Hạn dùng", "còn 25 ngày (hết hạn 12/10/2026)")
    conv.set_fact("Lần cuối đến", "112 ngày trước")

    temp = args.temp
    print("╔" + "═" * 59 + "╗")
    print(f"║  CareDesk Assistant [{args.persona}] — /help để xem lệnh" + " " * 12 + "║")
    print("╚" + "═" * 59 + "╝")

    while True:
        try:
            line = input("\nBạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue

        # ---------- lệnh ----------
        if line.startswith("/"):
            cmd, *rest = line.split(maxsplit=1)
            arg = rest[0] if rest else ""
            if cmd == "/quit":
                break
            elif cmd == "/help":
                print(HELP)
            elif cmd == "/stats":
                print(" ", conv.stats())
                print(llm.usage.report())
            elif cmd == "/system":
                print(conv._system())
            elif cmd == "/facts":
                for k, v in conv.facts.items():
                    print(f"  {k}: {v}")
            elif cmd == "/fact" and "=" in arg:
                k, v = arg.split("=", 1)
                conv.set_fact(k.strip(), v.strip())
                print(f"  đã thêm: {k.strip()}")
            elif cmd == "/temp":
                temp = float(arg); print(f"  temperature = {temp}")
            elif cmd == "/clear":
                conv.messages.clear(); conv.summary = ""
                print("  đã xoá lịch sử (facts giữ nguyên)")
            elif cmd == "/save":
                Path("conversations").mkdir(exist_ok=True)
                f = Path("conversations") / f"{datetime.now():%Y-%m-%d-%H%M}.json"
                f.write_text(json.dumps(
                    {"system": conv.base_system, "facts": conv.facts,
                     "summary": conv.summary, "messages": conv.messages},
                    ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  đã lưu {f}")
            elif cmd == "/load":
                d = json.loads(Path(arg).read_text(encoding="utf-8"))
                conv.facts, conv.summary, conv.messages = d["facts"], d["summary"], d["messages"]
                print(f"  đã nạp {len(conv.messages)//2} lượt")
            else:
                print("  lệnh không hợp lệ, gõ /help")
            continue

        # ---------- hỏi model ----------
        conv.messages.append({"role": "user", "content": line})
        conv._compress()

        def call():
            sys.stdout.write("Bot: "); sys.stdout.flush()
            return llm.stream(
                "\n".join(f"{m['role']}: {m['content']}" for m in conv.messages),
                system=conv._system(), temperature=temp, max_tokens=500,
                on_text=lambda c: (sys.stdout.write(c), sys.stdout.flush()))

        r = with_fallback(
            primary=lambda: with_retry(call, max_attempts=3),
            fallback=lambda: None,
            on_fallback=lambda e: print(f"\n  [lỗi: {type(e).__name__} — thử lại sau]"))

        if r is None:
            conv.messages.pop()
            continue

        conv.messages.append({"role": "assistant", "content": r.text})
        print(f"\n\n[in={r.input_tokens} out={r.output_tokens} | ${r.cost:.4f} | "
              f"TTFT {getattr(r, 'ttft', 0):.1f}s | phiên ${llm.usage.cost:.4f}]")

    print("\n" + "=" * 60)
    print(llm.usage.report())
    print(f"Số lượt: {len(conv.messages)//2}")


if __name__ == "__main__":
    main()
```

---

## 3. Việc phải làm

1. **Chạy 20 lượt hội thoại thật** với persona `spa`. Ghi lại: chi phí tổng, số lần nén, có lần nào mất thông tin không.
2. **Thử phá**: nhập câu dài 3000 từ; nhập lệnh sai; ngắt mạng giữa chừng; Ctrl+C khi đang stream. Ghi lại cái nào làm chết chương trình → sửa.
3. **Kiểm tra log**: mở `logs/*.jsonl`, xác nhận mỗi lượt có một dòng đủ trường.

---

## 4. Tiêu chí PASS/FAIL

- [ ] Chạy 20 lượt không crash
- [ ] Nén lịch sử tự động, facts không mất
- [ ] Stream mượt, hiện TTFT
- [ ] Ngắt mạng → có retry, không chết
- [ ] `/save` + `/load` khôi phục đúng hội thoại
- [ ] Log JSONL đầy đủ
- [ ] Báo cáo chi phí đúng khi thoát
- [ ] Đã thử phá bằng 4 cách, sửa hết lỗi tìm được

**Mở rộng:** thêm `/model <tên>` đổi model giữa chừng và so sánh chất lượng/chi phí.

---

## 5. Quiz + tổng kết tuần 3

```powershell
python quiz\quiz.py --day 21
python quiz\quiz.py --exam 15 21
```

Ghi `progress/notes/week3-review.md`: 3 thứ khó nhất tuần này, chi phí API đã tiêu, thứ bạn sẽ tái sử dụng ở Phase 6.

```powershell
git add . ; git commit -m "day 21: CLI chatbot - tuần 3 hoàn thành"
```
