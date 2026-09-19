# NGÀY 60 — Workflow vs Agent

> Phase 4 · 30' lý thuyết — 10' tài liệu — 60' code — 20' note
> Ngày này nặng về **quyết định kiến trúc**, nhẹ về code. Nó tiết kiệm cho bạn hàng tuần làm lại.

## 🎯 Mục tiêu

Biết khi nào dùng workflow cố định, khi nào dùng agent tự quyết — và **chứng minh bằng số liệu** trên chính bài toán của bạn.

---

## 1. Lý thuyết cốt lõi (30 phút)

### 1.1 Phổ từ cứng đến mềm

```
CODE THUẦN ──► WORKFLOW ──► WORKFLOW + LLM ──► AGENT có ràng buộc ──► AGENT tự do
  rẻ nhất                                                              đắt nhất
  đoán được                                                         khó đoán nhất
  không linh hoạt                                                  linh hoạt nhất
```

> **Quy tắc:** luôn chọn mức **cứng nhất** vẫn giải quyết được bài toán. Đừng dùng agent cho việc workflow làm được.

### 1.2 Bảng quyết định

| Câu hỏi | Nếu CÓ → |
|---|---|
| Các bước có biết trước không? | Workflow |
| Số bước có cố định không? | Workflow |
| Thứ tự có thay đổi theo dữ liệu không? | Agent |
| Có cần quyết định dùng tool nào lúc chạy không? | Agent |
| Sai sót có tốn tiền thật không? | Workflow + người duyệt |
| Có cần giải thích chính xác vì sao hệ thống làm vậy? | Workflow |
| Đầu vào có đa dạng không lường trước không? | Agent |

### 1.3 So sánh trên CareDesk-AI

| Chức năng | Chọn | Vì sao |
|---|---|---|
| Phát hiện khách quá hạn | **SQL thuần** | luật rõ ràng, phải chính xác 100%, chạy trên 3.000 khách mỗi đêm |
| Tính giá trị cơ hội | **Code** | công thức cố định, kiểm toán được |
| Giải thích vì sao khách này | **Workflow + LLM** | 1 bước LLM, đầu vào có cấu trúc |
| Soạn tin nhắn | **Workflow + LLM** | 1 bước, có validate |
| Trả lời câu hỏi tự do của nhân viên | **Agent** | không biết trước cần tool nào |
| Nghiên cứu nhà cung cấp (Project #3) | **Agent** | số bước phụ thuộc dữ liệu tìm được |

Nhìn bảng này: **phần lớn sản phẩm là workflow**, agent chỉ ở chỗ thật sự cần.

### 1.4 Năm mẫu workflow phổ biến

```
1. CHAIN       : A → B → C                      (Ngày 26)
2. ROUTER      : phân loại → chọn nhánh xử lý
3. PARALLEL    : chạy N việc song song → gộp
4. EVALUATOR   : sinh → chấm → sửa (Ngày 27)
5. ORCHESTRATOR: LLM lập kế hoạch, code thực thi từng bước
```

Mẫu 5 là "agent nhẹ": LLM chỉ quyết định **kế hoạch một lần**, sau đó code chạy theo kế hoạch đó. Rẻ và đoán được hơn agent thật.

---

## 2. Tài liệu (10 phút)

| Nguồn | Link |
|---|---|
| Anthropic — Building effective agents | https://www.anthropic.com/research/building-effective-agents |

Đọc kỹ phần phân biệt workflow và agent. Đây là tài liệu quan trọng nhất của Phase 4.

---

## 3. Thực hành (60 phút)

`exercises/day60/workflow_vs_agent.py`:

```python
"""Ngày 60: cùng bài toán, 3 cách làm, đo 4 chỉ số."""
import json
import time

from leanai_core.agent import Agent
from leanai_core.llm import LLMClient
from exercises.day52.toolset import registry, _derive, CUSTOMERS

llm = LLMClient()

# ---------- CÁCH 1: CODE THUẦN ----------
def approach_code(min_days: int = 90):
    t0 = time.time()
    out = []
    for cid in CUSTOMERS:
        d = _derive(cid)
        if d["vang_mat_ngay"] >= min_days and d["buoi_con_lai"] > 0:
            out.append({"id": cid, "ten": d["ten"],
                        "gia_tri": d["gia_tri_chua_dung"],
                        "vang": d["vang_mat_ngay"]})
    out.sort(key=lambda x: -x["gia_tri"])
    return out, time.time() - t0, 0.0


# ---------- CÁCH 2: WORKFLOW (code lọc + LLM giải thích) ----------
def approach_workflow(min_days: int = 90):
    t0 = time.time()
    candidates, _, _ = approach_code(min_days)
    cost = 0.0
    for c in candidates:
        r = llm.complete(
            f"<data>{json.dumps(c, ensure_ascii=False)}</data>\n\n"
            "Giải thích cho nhân viên vì sao đây là cơ hội doanh thu. "
            "Đúng 2 câu, mỗi câu dẫn 1 con số từ <data>.",
            temperature=0.2, max_tokens=120, tag="wf-explain")
        c["giai_thich"] = r.text.strip()
        cost += r.cost
    return candidates, time.time() - t0, cost


# ---------- CÁCH 3: AGENT ----------
def approach_agent(min_days: int = 90):
    t0 = time.time()
    agent = Agent(registry, max_steps=10, max_cost=0.20)
    run = agent.run(
        f"Tìm tất cả khách vắng mặt từ {min_days} ngày trở lên mà còn buổi chưa dùng. "
        "Với mỗi khách, nêu tên, giá trị chưa dùng và 1 câu giải thích vì sao nên liên hệ. "
        "Sắp xếp theo giá trị giảm dần.")
    return run.answer, time.time() - t0, run.cost


if __name__ == "__main__":
    RUNS = 3
    print(f"{'cách':<14} {'giây':>8} {'$/lần':>10} {'ổn định':>10} {'kiểm toán':>10}")
    for name, fn, stable, auditable in (
        ("code thuần", approach_code, "100%", "có"),
        ("workflow", approach_workflow, "cao", "có"),
        ("agent", approach_agent, "?", "khó"),
    ):
        secs, costs, outs = [], [], []
        for _ in range(RUNS):
            o, s, c = fn()
            secs.append(s); costs.append(c); outs.append(str(o))
        same = len(set(outs)) == 1
        print(f"{name:<14} {sum(secs)/RUNS:>8.2f} {sum(costs)/RUNS:>10.5f} "
              f"{('100%' if same else f'{len(set(outs))} kết quả khác nhau'):>10} {auditable:>10}")

    print("\nKết luận cần rút ra: với bài toán CÓ LUẬT RÕ RÀNG, agent chỉ thêm "
          "chi phí, độ trễ và tính không đoán trước — không thêm giá trị.")
```

---

## 4. Bài tập

**Bài 1 — Bảng quyết định cho CareDesk-AI.** Liệt kê **12 chức năng** của sản phẩm, với mỗi cái chọn: code / workflow / workflow+LLM / agent, kèm lý do dựa trên bảng 1.2. Lưu `progress/notes/day60-architecture-decisions.md`.
*Đây là tài liệu bạn sẽ dùng thẳng ở Ngày 77.*

**Bài 2 — Orchestrator pattern.** Cài mẫu 5: LLM lập kế hoạch JSON `{"steps":[{"tool":...,"args":...}]}` một lần, code thực thi tuần tự. So với agent thật: chi phí, latency, tỉ lệ thành công trên 10 nhiệm vụ.

**Bài 3 — Chi phí quy mô.** Với 3.000 khách, quét mỗi ngày: chi phí/tháng nếu dùng code thuần, workflow, agent? Con số này quyết định mô hình giá sản phẩm của bạn.

---

## 5. Quiz

```powershell
python quiz\quiz.py --day 60 ; python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Có bảng quyết định 12 chức năng, mỗi dòng có lý do
- [ ] Chứng minh bằng số: agent không phù hợp cho bài toán có luật rõ ràng
- [ ] Cài được orchestrator pattern và so sánh với agent
- [ ] Tính được chi phí/tháng ở quy mô 3.000 khách cho cả 3 cách
- [ ] Quiz ≥ 80%
