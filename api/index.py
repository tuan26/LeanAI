"""Entry point cho Vercel.

Vercel rewrite mọi URL về `/api/index/<đường-dẫn-gốc>`, nên FastAPI sẽ nhận
path `/api/index/healthz` thay vì `/healthz` và trả 404.

StripPrefix cắt lại tiền tố đó trước khi đưa vào app. Middleware chỉ áp dụng
ở file này, nên chạy local hoặc Docker không bị ảnh hưởng gì.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.server import app as _app  # noqa: E402

PREFIX = "/api/index"


class StripPrefix:
    """Cắt tiền tố Vercel thêm vào. Không có tiền tố thì để nguyên."""

    def __init__(self, inner, prefix: str = PREFIX):
        self.inner = inner
        self.prefix = prefix

    async def __call__(self, scope, receive, send):
        if scope.get("type") in ("http", "websocket"):
            path = scope.get("path", "")
            if path == self.prefix or path.startswith(self.prefix + "/"):
                new = path[len(self.prefix):] or "/"
                scope = dict(scope)
                scope["path"] = new
                scope["raw_path"] = new.encode()
        await self.inner(scope, receive, send)


app = StripPrefix(_app)

__all__ = ["app"]
