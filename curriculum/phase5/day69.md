# NGÀY 69 — Tracing: viewer & debug

> Phase 5 · 15' lý thuyết — 10' tài liệu — 85' code — 10' note

## 🎯 Mục tiêu

Xem lại trace, tìm nút thắt cổ chai, và **sửa được một vấn đề thật** dựa trên số liệu.

---

## 1. Lý thuyết cốt lõi (15 phút)

### 1.1 Ba câu hỏi trace viewer phải trả lời

```
1. Thời gian đi đâu?        → span nào chiếm % lớn nhất
2. Tiền đi đâu?             → span LLM nào tốn nhất
3. Vì sao request này sai?  → xem đúng dữ liệu vào/ra từng tầng
```

### 1.2 Quy trình tối ưu dựa trên trace

```
1. Gom 100 trace gần nhất
2. Tính p50/p95 cho TỪNG span
3. Chọn span có (p95 × tần suất) lớn nhất  ← nút thắt thật
4. Tối ưu ĐÚNG span đó
5. Đo lại, so sánh
```

Sai lầm phổ biến: tối ưu span mình *nghĩ* là chậm, không phải span *đo được* là chậm.

### 1.3 Ba mẫu vấn đề hay gặp

| Triệu chứng trong trace | Nguyên nhân thường gặp |
|---|---|
| `embed_query` chậm bất thường | không cache, gọi API mỗi lần |
| `rerank` chiếm > 30% thời gian | rerank quá nhiều ứng viên |
| `llm_answer` input_tokens rất lớn | context builder không cắt đúng |
| nhiều span `tool` lặp cùng tham số | agent đi vòng (Ngày 55) |

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Brendan Gregg — USE method | https://www.brendangregg.com/usemethod.html |
| OpenTelemetry — Traces | https://opentelemetry.io/docs/concepts/signals/traces/ |

---

## 3. Thực hành (85 phút)

`exercises/day69/trace_viewer.py`:

```python
"""Xem và phân tích trace."""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

TRACE_DIR = Path("logs/traces")


def load_traces(day: str = "") -> list[dict]:
    day = day or f"{datetime.now():%Y-%m-%d}"
    path = TRACE_DIR / f"{day}.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def print_tree(trace: dict) -> None:
    spans = trace["spans"]
    children = defaultdict(list)
    for s in spans:
        children[s["parent_id"]].append(s)
    total = trace["total_ms"] or 1

    def walk(parent: str, depth: int = 0):
        for s in children[parent]:
            pct = s["ms"] / total * 100
            bar = "█" * max(int(pct / 4), 0)
            attrs = " ".join(f"{k}={v}" for k, v in list(s["attrs"].items())[:4])
            err = f"  ❌ {s['error']}" if s["error"] else ""
            print(f"{'  ' * depth}├─ {s['name']:<20} {s['ms']:>8.1f}ms "
                  f"{pct:>5.1f}% {bar:<12} {attrs[:55]}{err}")
            walk(s["span_id"], depth + 1)

    print(f"\nTRACE {trace['trace_id']}  tenant={trace.get('tenant_id','-')}  "
          f"tổng {total:.0f}ms")
    walk("")


def bottleneck_report(traces: list[dict], top: int = 10) -> None:
    stats: dict[str, list[float]] = defaultdict(list)
    costs: dict[str, float] = defaultdict(float)
    errors: dict[str, int] = defaultdict(int)
    for t in traces:
        for s in t["spans"]:
            stats[s["name"]].append(s["ms"])
            costs[s["name"]] += float(s["attrs"].get("cost", 0) or 0)
            if s["error"]:
                errors[s["name"]] += 1

    print(f"\n{'span':<22}{'n':>5}{'p50':>9}{'p95':>9}{'tổng s':>10}{'$':>10}{'lỗi':>6}")
    print("-" * 74)
    rows = []
    for name, vals in stats.items():
        vals.sort()
        p50 = statistics.median(vals)
        p95 = vals[max(int(len(vals) * 0.95) - 1, 0)]
        rows.append((sum(vals), name, len(vals), p50, p95, costs[name], errors[name]))
    for total, name, n, p50, p95, cost, err in sorted(rows, reverse=True)[:top]:
        print(f"{name:<22}{n:>5}{p50:>9.1f}{p95:>9.1f}{total/1000:>10.1f}"
              f"{cost:>10.4f}{err:>6}")

    if rows:
        worst = max(rows)
        print(f"\n👉 Nút thắt lớn nhất: '{worst[1]}' — "
              f"chiếm {worst[0]/sum(r[0] for r in rows):.0%} tổng thời gian")


def slowest(traces: list[dict], n: int = 5) -> None:
    print(f"\n=== {n} REQUEST CHẬM NHẤT ===")
    for t in sorted(traces, key=lambda x: -x["total_ms"])[:n]:
        print(f"  {t['total_ms']:>8.0f}ms  {t['trace_id']}")


def failures(traces: list[dict]) -> None:
    bad = [t for t in traces if any(s["error"] for s in t["spans"])]
    print(f"\n=== {len(bad)}/{len(traces)} TRACE CÓ LỖI ===")
    for t in bad[:5]:
        errs = [f"{s['name']}: {s['error']}" for s in t["spans"] if s["error"]]
        print(f"  {t['trace_id']}: {errs[0][:90]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("trace_id", nargs="?", default="")
    ap.add_argument("--day", default="")
    a = ap.parse_args()

    traces = load_traces(a.day)
    if not traces:
        raise SystemExit("Chưa có trace nào. Chạy Ngày 68 trước.")

    if a.trace_id:
        for t in traces:
            if t["trace_id"].startswith(a.trace_id):
                print_tree(t)
                break
        else:
            print(f"Không tìm thấy trace {a.trace_id}")
    else:
        print(f"Đã nạp {len(traces)} trace")
        bottleneck_report(traces)
        slowest(traces)
        failures(traces)
        print_tree(max(traces, key=lambda x: x["total_ms"]))
```

---

## 4. Bài tập

**Bài 1 — Báo cáo nút thắt.** Chạy 100 request qua pipeline, chạy viewer. Xác định span chiếm nhiều thời gian nhất và span tốn nhiều tiền nhất. Có phải cùng một span không?

**Bài 2 — Tối ưu một thứ.** Chọn nút thắt số 1. Tối ưu **một** thay đổi (giảm ứng viên rerank / bật cache / giảm k). Chạy lại 100 request. Lập bảng trước/sau: p50, p95, chi phí, **và chất lượng** (dùng eval Ngày 67).
> Quan trọng: nếu tối ưu làm giảm chất lượng, ghi lại rõ ràng và cân nhắc lại.

**Bài 3 — Debug một ca sai.** Lấy 1 eval case thất bại, mở trace. Xác định tầng nào gây lỗi: truy hồi không có tài liệu đúng? Context builder cắt nhầm? LLM bỏ qua tài liệu? Ghi kết luận + cách sửa.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 69 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Viewer in được cây span với % thời gian
- [ ] Báo cáo p50/p95/chi phí theo từng span
- [ ] Xác định đúng nút thắt bằng số liệu (không đoán)
- [ ] Một vòng tối ưu có bảng trước/sau, **kèm kiểm tra chất lượng**
- [ ] Debug được 1 eval case thất bại bằng trace
- [ ] Quiz ≥ 80%
