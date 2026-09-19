# NGÀY 18 — Conversation & memory

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Quản lý hội thoại nhiều lượt mà **không để chi phí tăng vô hạn**.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Chi phí hội thoại tăng theo bình phương

Mỗi lượt bạn gửi lại **toàn bộ** lịch sử:

```
Lượt 1: gửi 100 token
Lượt 2: gửi 100 + 150 + 100 = 350
Lượt 3: gửi 350 + 150 + 100 = 600
...
Lượt 20: gửi ~10.000 token cho MỘT câu hỏi ngắn
```

Tổng chi phí của N lượt ≈ **O(N²)**. Đây là lý do chatbot không kiểm soát lịch sử sẽ "đốt tiền" âm thầm.

### 1.2 Bốn chiến lược quản lý bộ nhớ

| Chiến lược | Cách làm | Ưu | Nhược |
|---|---|---|---|
| **Full** | gửi tất cả | không mất thông tin | O(N²), vỡ context |
| **Sliding window** | giữ k lượt gần nhất | đơn giản, rẻ | quên thông tin đầu |
| **Summarize** ⭐ | tóm tắt phần cũ, giữ nguyên phần mới | cân bằng tốt | tốn 1 lần gọi LLM, mất chi tiết |
| **Facts extraction** | trích sự kiện quan trọng ra store riêng | chính xác, bền | phức tạp nhất |

Sản phẩm thật thường dùng **summarize + facts**: tóm tắt cho ngữ cảnh chung, facts cho dữ liệu cứng (tên, số điện thoại, gói dịch vụ).

### 1.3 Nguyên tắc vàng

> Thông tin **cứng** (tên khách, mã gói, số buổi còn lại) **không bao giờ** để trong lịch sử hội thoại. Nó thuộc về database, và được chèn vào system prompt mỗi lượt.

Lý do: tóm tắt có thể làm mất hoặc sai lệch con số. Ngày 13 đã dạy bạn điều này.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Multi-turn conversations | https://docs.anthropic.com/en/docs/build-with-claude/conversations |
| Anthropic — Prompt caching (giảm chi phí lịch sử) | https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching |

---

## 3. Thực hành (80 phút)

`leanai_core/memory.py`:

```python
"""Quản lý bộ nhớ hội thoại: cửa sổ trượt + tóm tắt + facts."""
from __future__ import annotations

import tiktoken
from .llm import LLMClient

ENC = tiktoken.get_encoding("cl100k_base")


def ntok(x) -> int:
    if isinstance(x, str):
        return len(ENC.encode(x))
    return sum(len(ENC.encode(m["content"])) for m in x)


class Conversation:
    def __init__(self, llm: LLMClient, system: str = "",
                 max_history_tokens: int = 2000, keep_recent: int = 4):
        self.llm = llm
        self.base_system = system
        self.messages: list[dict] = []
        self.summary = ""
        self.facts: dict[str, str] = {}      # dữ liệu cứng, không bao giờ tóm tắt
        self.max_history_tokens = max_history_tokens
        self.keep_recent = keep_recent

    # ---- facts: nguồn sự thật, luôn nguyên vẹn ----
    def set_fact(self, key: str, value: str) -> None:
        self.facts[key] = value

    def _system(self) -> str:
        parts = [self.base_system]
        if self.facts:
            parts.append("THÔNG TIN XÁC THỰC (lấy từ hệ thống, luôn đúng):\n" +
                         "\n".join(f"- {k}: {v}" for k, v in self.facts.items()))
        if self.summary:
            parts.append(f"TÓM TẮT PHẦN TRƯỚC CỦA HỘI THOẠI:\n{self.summary}")
        return "\n\n".join(p for p in parts if p)

    # ---- nén lịch sử khi vượt ngưỡng ----
    def _compress(self) -> None:
        if ntok(self.messages) <= self.max_history_tokens:
            return
        old, recent = self.messages[:-self.keep_recent], self.messages[-self.keep_recent:]
        if not old:
            return
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in old)
        r = self.llm.complete(
            f"Tóm tắt hội thoại sau thành tối đa 120 từ. Giữ lại: yêu cầu của khách, "
            f"quyết định đã thống nhất, vấn đề chưa giải quyết. Bỏ lời chào và câu xã giao.\n\n"
            f"{self.summary}\n{transcript}",
            max_tokens=250, tag="nén hội thoại")
        self.summary = r.text.strip()
        self.messages = recent
        print(f"  [nén] {len(old)} lượt cũ -> tóm tắt {ntok(self.summary)} token")

    def ask(self, user_input: str, **kw) -> str:
        self.messages.append({"role": "user", "content": user_input})
        self._compress()
        r = self.llm.chat(self.messages, system=self._system(), tag="chat", **kw)
        self.messages.append({"role": "assistant", "content": r.text})
        return r.text

    def stats(self) -> dict:
        return {"lượt": len(self.messages) // 2,
                "token lịch sử": ntok(self.messages),
                "token tóm tắt": ntok(self.summary),
                "facts": len(self.facts)}
```

`exercises/day18/chat_memory.py` — thí nghiệm so sánh:

```python
from leanai_core.llm import LLMClient
from leanai_core.memory import Conversation

SYS = "Bạn là trợ lý đặt lịch của spa. Trả lời ngắn gọn, tối đa 40 từ."

TURNS = [
    "Chào em, chị muốn đặt lịch trị liệu da mặt.",
    "Chị tên Nguyễn Thị Lan, số điện thoại 0901234567.",
    "Chị muốn đặt vào chiều thứ 5 tuần này.",
    "À mà gói của chị còn mấy buổi nhỉ?",
    "Chị đổi sang thứ 6 được không?",
    "Chi nhánh Quận 7 có chỗ đỗ ô tô không em?",
    "Vậy chốt thứ 6 nhé.",
    "Nhắc lại giúp chị tên và số điện thoại chị đã cho em.",   # kiểm tra trí nhớ
]

for label, max_tok in (("KHÔNG NÉN", 100_000), ("CÓ NÉN", 400)):
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    llm = LLMClient()
    conv = Conversation(llm, system=SYS, max_history_tokens=max_tok, keep_recent=4)
    conv.set_fact("Khách hàng", "Nguyễn Thị Lan")
    conv.set_fact("Gói hiện tại", "Trị liệu da mặt 10 buổi, còn 4 buổi")
    conv.set_fact("Hạn sử dụng", "còn 25 ngày")

    for t in TURNS:
        print(f"\nKhách: {t}")
        print(f"Bot  : {conv.ask(t)}")

    print(f"\n{conv.stats()}")
    print(llm.usage.report())
```

### Quan sát bắt buộc

1. Lượt cuối ("nhắc lại tên và số điện thoại") — bản CÓ NÉN có trả lời đúng không? Nếu đúng, nhờ đâu? (Gợi ý: facts, không phải tóm tắt.)
2. Chênh lệch chi phí giữa hai bản là bao nhiêu %?
3. Câu "gói còn mấy buổi" — thông tin đến từ facts hay bị model bịa?

---

## 4. Bài tập

**Bài 1 — Đo O(N²).** Chạy hội thoại 20 lượt với cả 2 chiến lược, ghi chi phí tích luỹ sau mỗi lượt. Lập bảng và nhận xét đường cong.

**Bài 2 — Trích facts tự động.** Viết `extract_facts(text) -> dict` dùng LLM (temperature=0) trích tên, SĐT, ngày hẹn, dịch vụ từ câu của khách và tự động gọi `set_fact`. Cẩn thận: chỉ ghi khi model **chắc chắn**, có trường `confidence`.

**Bài 3 — Bẫy mất thông tin.** Thiết kế một hội thoại 15 lượt trong đó thông tin quan trọng xuất hiện ở lượt 2, rồi được hỏi lại ở lượt 15. Chạy với 3 chiến lược (full / sliding window / summarize+facts). Chiến lược nào giữ đúng? Ghi kết quả.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 18
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `Conversation` tự nén khi vượt ngưỡng, có in log nén
- [ ] Facts được giữ nguyên vẹn qua nén (chứng minh bằng lượt hỏi lại)
- [ ] Có bảng chi phí tích luỹ 20 lượt của 2 chiến lược
- [ ] Giải thích được vì sao dữ liệu cứng không nên nằm trong lịch sử
- [ ] Quiz ≥ 80%
