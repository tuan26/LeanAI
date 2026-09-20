"""Entry point cho Vercel — runtime Python nhan bien app ASGI o day."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.server import app  # noqa: E402

__all__ = ["app"]
