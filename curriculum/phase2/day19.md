# NGÀY 19 — Streaming

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Stream được output và **đo TTFT** — chỉ số trải nghiệm quan trọng nhất của sản phẩm LLM.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Vì sao streaming quan trọng

```
KHÔNG STREAM:  [------------ 8 giây im lặng ------------] toàn bộ câu trả lời
CÓ STREAM:     [0.6s] chữ đầu → chữ → chữ → ... → xong lúc 8s
```

Tổng thời gian **như nhau**. Nhưng cảm nhận người dùng khác hẳn: 0.6 giây so với 8 giây chờ trong vô định.

### 1.2 Ba chỉ số latency phải đo

| Chỉ số | Nghĩa | Ngưỡng tốt |
|---|---|---|
| **TTFT** (time to first token) | từ lúc gửi đến chữ đầu tiên | < 1s |
| **TPS** (tokens per second) | tốc độ sinh | > 30 tok/s |
| **Total** | tổng thời gian | tuỳ tác vụ |

`Total ≈ TTFT + output_tokens / TPS`

TTFT phụ thuộc **độ dài input** (nhớ O(n²) Ngày 6). Total phụ thuộc **độ dài output**.

### 1.3 Khi nào KHÔNG nên stream

| Tình huống | Lý do |
|---|---|
| Output là JSON cần parse | phải chờ đủ mới parse được |
| Cần validate trước khi hiện | không thể rút lại chữ đã hiện |
| Batch job chạy nền | không có ai nhìn |
| Kết quả sẽ qua guardrail kiểm duyệt | nguy cơ hiện nội dung xấu rồi mới chặn |

Trong CareDesk-AI: **stream** phần giải thích cho nhân viên đọc; **không stream** phần soạn tin nhắn (phải qua kiểm duyệt trước khi hiện).

### 1.4 Cấu trúc sự kiện stream

```
message_start        → metadata, usage input
content_block_delta  → từng mảnh text   ← cái bạn hiển thị
message_delta        → usage output, stop_reason
message_stop         → kết thúc
```

Lỗi giữa chừng vẫn có thể xảy ra **sau khi** đã hiện nửa câu trả lời. Phải xử lý.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Streaming Messages | https://docs.anthropic.com/en/api/messages-streaming |
| Server-Sent Events (MDN) | https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events |

---

## 3. Thực hành (80 phút)

Bổ sung vào `leanai_core/llm.py`:

```python
    def stream(self, prompt: str, *, system: str = "", temperature: float = 0.0,
               max_tokens: int = 1024, tag: str = "stream",
               on_text=None) -> LLMResponse:
        """Stream output. on_text(chunk) được gọi cho mỗi mảnh."""
        import time
        kwargs = dict(model=self.model, max_tokens=max_tokens,
                      temperature=temperature,
                      messages=[{"role": "user", "content": prompt}])
        if system:
            kwargs["system"] = system

        t0 = time.time()
        ttft = None
        chunks: list[str] = []

        with self.client.messages.stream(**kwargs) as s:
            for text in s.text_stream:
                if ttft is None:
                    ttft = time.time() - t0
                chunks.append(text)
                if on_text:
                    on_text(text)
            final = s.get_final_message()

        latency = time.time() - t0
        cost = (final.usage.input_tokens * cfg.PRICE_IN
                + final.usage.output_tokens * cfg.PRICE_OUT) / 1e6
        resp = LLMResponse(
            text="".join(chunks), input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
            stop_reason=final.stop_reason or "", latency=latency,
            cost=cost, model=self.model)
        resp.ttft = ttft                      # gắn thêm thuộc tính
        resp.tps = final.usage.output_tokens / max(latency - (ttft or 0), 0.001)
        self.usage.add(resp, tag)
        log_event("llm_stream", tag=tag, ttft=round(ttft or 0, 3),
                  tps=round(resp.tps, 1), latency=round(latency, 3),
                  output_tokens=resp.output_tokens, cost=round(cost, 6))
        return resp
```

`exercises/day19/stream_bench.py`:

```python
"""Ngày 19: đo TTFT và TPS, xem input dài ảnh hưởng thế nào."""
import sys
from leanai_core.llm import LLMClient

llm = LLMClient()

FILLER = "Phòng khám cam kết chất lượng dịch vụ và trải nghiệm khách hàng tốt nhất. "

def show(chunk: str) -> None:
    sys.stdout.write(chunk)
    sys.stdout.flush()

print("=== Trải nghiệm streaming ===")
r = llm.stream("Giải thích RAG cho chủ spa không rành công nghệ, khoảng 120 từ.",
               max_tokens=400, on_text=show)
print(f"\n\nTTFT={r.ttft:.2f}s  TPS={r.tps:.0f}  total={r.latency:.2f}s")

print("\n=== TTFT theo độ dài input ===")
print(f"{'input token':>12} {'TTFT':>7} {'TPS':>6} {'total':>7}")
for n in (0, 200, 1000, 3000):
    prompt = FILLER * n + "\n\nTóm tắt nội dung trên trong 1 câu."
    r = llm.stream(prompt, max_tokens=100, tag=f"input-{n}")
    print(f"{r.input_tokens:>12} {r.ttft:>7.2f} {r.tps:>6.0f} {r.latency:>7.2f}")

print("\n=== TTFT vs Total theo độ dài OUTPUT ===")
for n in (50, 200, 800):
    r = llm.stream(f"Viết đúng {n} từ về chăm sóc da.", max_tokens=n*2, tag=f"out-{n}")
    print(f"  yêu cầu {n:>3} từ: out={r.output_tokens:>4} tok  "
          f"TTFT={r.ttft:.2f}s  total={r.latency:.2f}s")

print("\n" + llm.usage.report())
```

### Quan sát bắt buộc

1. TTFT tăng thế nào khi input dài ra? Có tuyến tính không?
2. TTFT có thay đổi khi output dài ra không? (Đáp án đúng: **không** — và đó là điểm mấu chốt.)
3. TPS có ổn định giữa các lần chạy không?

---

## 4. Bài tập

**Bài 1 — Bảng latency.** Chạy mỗi cấu hình 3 lần, lấy trung vị. Lập bảng `input_tokens | TTFT | TPS | total`. Vẽ nhận xét: *"để giảm thời gian chờ của người dùng, tôi nên tối ưu ___ trước."*

**Bài 2 — Stream có huỷ.** Thêm khả năng dừng giữa chừng khi người dùng nhấn Ctrl+C: bắt `KeyboardInterrupt`, vẫn ghi log phần đã nhận và chi phí đã phát sinh. (Quan trọng: **huỷ không có nghĩa là không mất tiền**.)

**Bài 3 — Quyết định sản phẩm.** Trong `progress/notes/day19.md`, điền bảng cho CareDesk-AI:

| Chức năng | Stream? | Lý do |
|---|---|---|
| Giải thích cơ hội doanh thu cho nhân viên | | |
| Soạn tin nhắn Zalo | | |
| Trích xuất dữ liệu khách ra JSON | | |
| Quét 3000 khách hàng ban đêm | | |

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 19
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Stream hiển thị từng chữ, không giật
- [ ] Đo được TTFT và TPS, ghi vào log
- [ ] Có bảng số liệu TTFT theo độ dài input
- [ ] Giải thích được vì sao output dài không ảnh hưởng TTFT
- [ ] Điền xong bảng quyết định stream cho CareDesk-AI
- [ ] Quiz ≥ 80%
