"""Lớp lưu trữ thay thế được.

- FileStorage  : ghi ra đĩa — dùng khi chạy local / Docker (mặc định)
- RedisStorage : Upstash Redis qua REST — dùng khi chạy serverless (Vercel)

Chọn backend bằng biến môi trường, không phải bằng sửa code:
    UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN  -> Redis
    không có                                           -> file

Chỉ dùng thư viện chuẩn: serverless khởi động nhanh hơn, ít phụ thuộc hơn.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

from . import config

TIMEOUT = 8


class Storage(Protocol):
    def load(self, key: str, default: dict) -> dict: ...
    def save(self, key: str, data: dict) -> None: ...
    @property
    def name(self) -> str: ...


# ------------------------------------------------------------------ file
class FileStorage:
    """Ghi ra đĩa. Key được ánh xạ sang đường dẫn cố định để tương thích
    ngược với quiz/quiz.py và track.py — hai công cụ đó đọc thẳng file."""

    def __init__(self) -> None:
        self.paths = {
            "quiz_progress": Path(config.QUIZ_PROGRESS),
            "status": Path(config.STATUS_FILE),
        }

    @property
    def name(self) -> str:
        return f"file ({self.paths['quiz_progress'].parent})"

    def _path(self, key: str) -> Path:
        if key in self.paths:
            return self.paths[key]
        base = self.paths["status"].parent
        return base / f"{key}.json"

    def load(self, key: str, default: dict) -> dict:
        p = self._path(key)
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default

    def save(self, key: str, data: dict) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)          # ghi nguyên tử: mất điện giữa chừng không hỏng file


# ----------------------------------------------------------------- redis
class RedisStorage:
    """Upstash Redis REST. Mỗi key là một chuỗi JSON."""

    def __init__(self, url: str, token: str, prefix: str = "leanai") -> None:
        self.url = url.rstrip("/")
        self.token = token
        self.prefix = prefix

    @property
    def name(self) -> str:
        host = self.url.split("//")[-1].split(".")[0]
        return f"redis ({host}…)"

    def _cmd(self, *args: str) -> object:
        body = json.dumps(list(args)).encode()
        req = urllib.request.Request(
            self.url, data=body, method="POST",
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode()).get("result")

    def load(self, key: str, default: dict) -> dict:
        try:
            raw = self._cmd("GET", f"{self.prefix}:{key}")
        except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
            return default
        if not raw:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    def save(self, key: str, data: dict) -> None:
        self._cmd("SET", f"{self.prefix}:{key}",
                  json.dumps(data, ensure_ascii=False))


# ---------------------------------------------------------------- chọn
def build() -> Storage:
    url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    if url and token:
        return RedisStorage(url, token,
                            prefix=os.getenv("LEANAI_KEY_PREFIX", "leanai"))
    return FileStorage()


store: Storage = build()
