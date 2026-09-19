"""Cấu hình triển khai — đọc từ biến môi trường.

Mặc định: chạy local, không xác thực, ghi thẳng vào thư mục repo.
Khi deploy: đặt LEANAI_USER/LEANAI_PASS và LEANAI_DATA_DIR (volume).
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# --- mạng ---
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))

# --- xác thực ---
USER = os.getenv("LEANAI_USER", "")
PASS = os.getenv("LEANAI_PASS", "")
AUTH_ENABLED = bool(USER and PASS)

# --- dữ liệu ---
# Khi deploy, trỏ vào volume để tiến trình không mất khi container khởi động lại.
DATA_DIR = Path(os.getenv("LEANAI_DATA_DIR", "")) if os.getenv("LEANAI_DATA_DIR") else None
QUIZ_PROGRESS = (DATA_DIR / "quiz-progress.json") if DATA_DIR else ROOT / "quiz" / "progress.json"
STATUS_FILE = (DATA_DIR / "status.json") if DATA_DIR else ROOT / "progress" / "status.json"

# --- an toàn ---
EXPOSED = HOST not in ("127.0.0.1", "localhost", "::1")
# Mở ra ngoài mà không đặt mật khẩu -> chỉ cho ĐỌC, chặn mọi thao tác ghi.
READ_ONLY = _bool("LEANAI_READ_ONLY", EXPOSED and not AUTH_ENABLED)


def banner() -> str:
    lines = [f"  LeanAI  →  http://{HOST}:{PORT}"]
    if DATA_DIR:
        lines.append(f"  Dữ liệu : {DATA_DIR}")
    if AUTH_ENABLED:
        lines.append(f"  Xác thực: BẬT (user: {USER})")
    elif EXPOSED:
        lines.append("  ⚠ MỞ RA MẠNG NGOÀI MÀ KHÔNG CÓ MẬT KHẨU")
        lines.append("    → đang chạy CHẾ ĐỘ CHỈ ĐỌC, mọi thao tác ghi bị chặn.")
        lines.append("    → đặt LEANAI_USER và LEANAI_PASS để bật ghi.")
    if READ_ONLY and AUTH_ENABLED:
        lines.append("  Chế độ : CHỈ ĐỌC (LEANAI_READ_ONLY=1)")
    return "\n".join(lines)
