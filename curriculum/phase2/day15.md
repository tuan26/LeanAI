# NGÀY 15 — Python, API, JSON

> Phase 2 · 20' lý thuyết — 10' tài liệu — 80' code — 10' note

## 🎯 Mục tiêu

Nền móng kỹ thuật cho 75 ngày còn lại: gọi HTTP API, xử lý JSON, quản lý secret, cấu trúc dự án. Nếu bạn đã vững Python, hôm nay vẫn phải làm — vì phần **cấu trúc dự án** sẽ dùng đến Ngày 90.

---

## 1. Lý thuyết cốt lõi (20 phút)

### 1.1 Một request HTTP gồm gì

```
POST https://api.anthropic.com/v1/messages          ← URL + method
Headers:
  x-api-key: sk-ant-...                             ← xác thực
  content-type: application/json                    ← định dạng body
Body (JSON):
  {"model": "...", "messages": [...], "max_tokens": 1024}
                                    ↓
Response:
  status 200 + JSON body            ← thành công
  status 401 / 429 / 500            ← lỗi (Ngày 20 xử lý)
```

Mọi LLM API đều là dạng này. SDK chỉ là lớp bọc cho tiện.

### 1.2 Mã lỗi phải thuộc

| Mã | Nghĩa | Xử lý |
|---|---|---|
| 200 | OK | — |
| 400 | request sai (thiếu field, quá dài) | sửa code, **không retry** |
| 401 | sai API key | kiểm tra `.env` |
| 429 | vượt rate limit | **retry có backoff** |
| 500/529 | lỗi phía server | **retry có backoff** |

### 1.3 Quản lý secret — làm đúng ngay từ đầu

```
❌ api_key = "sk-ant-abc123"        trong code
❌ commit file .env lên git
✅ .env (đã gitignore) + os.getenv()
```

Key bị lộ trên GitHub sẽ bị bot quét trong **vài phút**. Đây không phải chuyện lý thuyết.

### 1.4 Cấu trúc dự án dùng suốt 90 ngày

```
leanai_core/
  __init__.py
  config.py        # đọc .env, giữ mọi hằng số ở 1 chỗ
  http.py          # gọi HTTP có retry
  logging.py       # log có cấu trúc (JSON lines)
```

Viết một lần, dùng 75 ngày. Đừng copy-paste `load_dotenv()` vào từng file.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| httpx quickstart | https://www.python-httpx.org/quickstart/ |
| Python JSON docs | https://docs.python.org/3/library/json.html |
| REST API status codes | https://developer.mozilla.org/en-US/docs/Web/HTTP/Status |

---

## 3. Thực hành (80 phút)

### Bước 1 — Module config dùng chung

`leanai_core/config.py`:

```python
"""Cấu hình tập trung. Mọi file khác import từ đây."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


class Config:
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
    DAILY_COST_LIMIT = float(os.getenv("DAILY_COST_LIMIT", "1.0"))

    # Giá USD / 1 triệu token — cập nhật theo bảng giá hiện hành
    PRICE_IN = 3.00
    PRICE_OUT = 15.00

    @classmethod
    def check(cls) -> None:
        missing = [k for k in ("ANTHROPIC_API_KEY",) if not getattr(cls, k)]
        if missing:
            raise SystemExit(f"Thiếu biến môi trường: {missing}. Kiểm tra file .env")


cfg = Config()
```

### Bước 2 — HTTP client thô (chưa dùng SDK, để hiểu bản chất)

`leanai_core/http.py`:

```python
"""Gọi HTTP có retry. Ngày 20 sẽ nâng cấp."""
import time
import httpx

RETRYABLE = {429, 500, 502, 503, 529}


def post_json(url: str, headers: dict, payload: dict,
              timeout: float = 60.0, max_retries: int = 3) -> dict:
    last = None
    for attempt in range(max_retries + 1):
        try:
            r = httpx.post(url, headers=headers, json=payload, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code not in RETRYABLE:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            last = f"HTTP {r.status_code}"
        except httpx.TimeoutException as e:
            last = f"timeout: {e}"

        if attempt < max_retries:
            wait = 2 ** attempt              # 1s, 2s, 4s
            print(f"  [retry {attempt+1}/{max_retries}] {last} -> chờ {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"Thất bại sau {max_retries} lần thử: {last}")
```

### Bước 3 — Gọi LLM API bằng HTTP thuần

`exercises/day15/raw_call.py`:

```python
"""Gọi Anthropic API bằng HTTP thuần — để thấy rõ SDK làm gì bên dưới."""
import json
from leanai_core.config import cfg
from leanai_core.http import post_json

cfg.check()

resp = post_json(
    "https://api.anthropic.com/v1/messages",
    headers={
        "x-api-key": cfg.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    },
    payload={
        "model": cfg.MODEL,
        "max_tokens": 200,
        "temperature": 0,
        "messages": [{"role": "user",
                      "content": "Trả lời đúng 1 câu: RAG là gì?"}],
    },
)

print(json.dumps(resp, ensure_ascii=False, indent=2)[:800])
print("\n--- Trích xuất ---")
print("Nội dung :", resp["content"][0]["text"])
print("Token in :", resp["usage"]["input_tokens"])
print("Token out:", resp["usage"]["output_tokens"])
print("Lý do dừng:", resp["stop_reason"])
```

Chạy:
```powershell
python -m exercises.day15.raw_call
```

### Bước 4 — Đọc kỹ response

In toàn bộ JSON. Trả lời được: `stop_reason` có những giá trị nào? Khi nào là `max_tokens`? Vì sao phải kiểm tra field này? (Gợi ý: `max_tokens` nghĩa là câu trả lời **bị cắt** — nếu bạn đang parse JSON thì sẽ hỏng.)

---

## 4. Bài tập

**Bài 1 — JSON an toàn.** Viết `leanai_core/jsonutil.py` với `safe_json_loads(text, default=None)`: thử parse, nếu hỏng thì tìm khối `{...}` đầu tiên bằng regex rồi parse lại, vẫn hỏng thì trả `default`. Test với 5 chuỗi hỏng khác nhau (thiếu ngoặc, có markdown fence ```json, có chữ thừa trước/sau).
*Bạn sẽ dùng hàm này rất nhiều từ Ngày 29.*

**Bài 2 — Ghi log có cấu trúc.** Viết `leanai_core/logging.py` với `log_event(event: str, **fields)` ghi một dòng JSON vào `logs/YYYY-MM-DD.jsonl`, luôn kèm timestamp. Gọi thử để log một request LLM (model, tokens, latency, cost).
*Đây là nền móng cho tracing ở Ngày 68.*

**Bài 3 — Test retry.** Gọi `post_json` tới `https://httpstat.us/429` và `https://httpstat.us/500`, xác nhận thấy log retry và cuối cùng ném lỗi. Gọi tới `https://httpstat.us/400` — xác nhận **không** retry.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 15
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Gọi được LLM API bằng HTTP thuần, in ra usage
- [ ] Có `leanai_core/` với config, http, jsonutil, logging
- [ ] `safe_json_loads` vượt qua 5 ca hỏng
- [ ] Retry hoạt động đúng với 429/500, không retry với 400
- [ ] `.env` không có trong `git status`
- [ ] Quiz ≥ 80%
