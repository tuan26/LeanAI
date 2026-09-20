#!/usr/bin/env python
"""Sao luu / khoi phuc tien trinh hoc tu ban LeanAI da deploy.

    python backup.py https://leanai.vercel.app -u tuan -p matkhau
    python backup.py https://leanai.vercel.app -u tuan -p matkhau --restore backups/2026-09-20.json
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def call(url: str, user: str, pw: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        url.rstrip("/") + path,
        data=json.dumps(body).encode() if body is not None else None,
        method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/json"})
    if user:
        tok = base64.b64encode(f"{user}:{pw}".encode()).decode()
        req.add_header("Authorization", f"Basic {tok}")
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="vd https://leanai.vercel.app")
    ap.add_argument("-u", "--user", default="")
    ap.add_argument("-p", "--password", default="")
    ap.add_argument("--restore", metavar="FILE", help="khôi phục từ file sao lưu")
    a = ap.parse_args()

    try:
        if a.restore:
            data = json.loads(Path(a.restore).read_text(encoding="utf-8"))
            print(f"Sắp GHI ĐÈ tiến trình trên {a.url}")
            print(f"  bản sao lưu: {data.get('exported_at','?')}")
            print(f"  {len(data['quiz_progress']['cards'])} thẻ quiz, "
                  f"{len(data['status']['days'])} ngày")
            if input("Gõ 'yes' để xác nhận: ").strip() != "yes":
                print("Đã huỷ."); return
            r = call(a.url, a.user, a.password, "/api/import", data)
            print(f"Đã khôi phục: {r['cards']} thẻ, {r['days']} ngày")
            return

        d = call(a.url, a.user, a.password, "/api/export")
        Path("backups").mkdir(exist_ok=True)
        f = Path("backups") / f"leanai-{date.today()}.json"
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        cards = len(d["quiz_progress"].get("cards", {}))
        days = len(d["status"].get("days", {}))
        passed = sum(1 for v in d["status"]["days"].values() if v.get("status") == "pass")
        print(f"Đã lưu {f}")
        print(f"  {passed}/90 ngày PASS · {cards} thẻ quiz · {days} ngày có ghi nhận")
    except urllib.error.HTTPError as e:
        print(f"Lỗi HTTP {e.code}: {e.read().decode()[:200]}")
        if e.code == 401:
            print("-> sai tài khoản/mật khẩu (LEANAI_USER / LEANAI_PASS)")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Không kết nối được: {e.reason}"); sys.exit(1)


if __name__ == "__main__":
    main()
