# NGÀY 5 — Embedding

> Phase 1 · 25' lý thuyết — 15' tài liệu — 70' code — 10' note

## 🎯 Mục tiêu

Hiểu embedding là gì, tự đo được độ tương đồng ngữ nghĩa, và nhận ra đây là **nền móng của toàn bộ Phase 3 (RAG)**.

---

## 1. Lý thuyết cốt lõi (25 phút)

### 1.1 Embedding = toạ độ ngữ nghĩa

Embedding biến một đoạn text thành vector số thực (thường 384–3072 chiều). Text có ý nghĩa gần nhau → vector gần nhau trong không gian.

```
"đặt lịch hẹn"    → [0.12, -0.45, 0.88, ...]  ┐
"book appointment"→ [0.14, -0.41, 0.85, ...]  ┘ rất gần nhau
"giá gói trị liệu"→ [0.91,  0.33, -0.12, ...]   xa
```

Điều kỳ diệu: **khác ngôn ngữ, khác từ ngữ, nhưng cùng ý nghĩa thì vẫn gần nhau**. Đây là thứ keyword search không bao giờ làm được.

### 1.2 Đo khoảng cách: cosine similarity

```
cos(A, B) = (A · B) / (|A| × |B|)     ∈ [-1, 1]
```

| Giá trị | Ý nghĩa thực tế (với embedding hiện đại) |
|---|---|
| > 0.85 | gần như trùng ý |
| 0.6 – 0.85 | liên quan rõ ràng |
| 0.4 – 0.6 | cùng chủ đề, khác ý |
| < 0.4 | không liên quan |

⚠️ Ngưỡng này **phụ thuộc model**. Không copy ngưỡng từ blog — phải tự đo trên dữ liệu của bạn (Ngày 35).

### 1.3 Ba loại embedding — đừng nhầm

| Loại | Sinh ra từ | Dùng để |
|---|---|---|
| **Token embedding** | bên trong LLM, mỗi token 1 vector | model tính toán nội bộ |
| **Sentence/document embedding** | model embedding riêng (`text-embedding-3-small`...) | **search, RAG, clustering** |
| Contextual embedding | lớp ẩn của LLM | nghiên cứu, ít dùng trong app |

Phase 3 bạn chỉ dùng loại thứ 2.

### 1.4 Vì sao embedding làm nên RAG

```
Câu hỏi user  ──embed──►  vector  ──tìm k vector gần nhất──►  đoạn tài liệu liên quan
                                            ▲
                          Tài liệu ──chunk──┴──embed──►  vector DB
```

Toàn bộ Phase 3 là kỹ thuật hoá sơ đồ này cho đủ tin cậy để bán tiền. Hôm nay bạn làm phiên bản thô sơ nhất.

### 1.5 Giới hạn phải biết trước

- Embedding **không hiểu phủ định tốt**: "có bảo hành" và "không bảo hành" có thể rất gần nhau. → Ngày 36 dùng hybrid search để chữa.
- Embedding **không hiểu số**: "gói 5 buổi" vs "gói 50 buổi" gần nhau. → Ngày 34 dùng metadata filter để chữa.
- Chất lượng phụ thuộc mạnh vào **tiếng Việt có được train không**. Luôn test trên dữ liệu Việt trước khi chọn model.

---

## 2. Tài liệu (15 phút)

| Nguồn | Link | Bắt buộc |
|---|---|---|
| Jay Alammar — Illustrated Word2vec | https://jalammar.github.io/illustrated-word2vec/ | ✅ |
| OpenAI Embeddings guide | https://platform.openai.com/docs/guides/embeddings | ✅ |
| TensorFlow Embedding Projector (trực quan 3D) | https://projector.tensorflow.org/ | nên chơi 5' |

---

## 3. Thực hành (70 phút)

### Phần A — Không cần API: tự cài similarity (20')

`exercises/day05/similarity.py`:

```python
"""Ngày 5A: cosine similarity từ con số 0."""
import math


def dot(a, b):    return sum(x * y for x, y in zip(a, b))
def norm(a):      return math.sqrt(sum(x * x for x in a))
def cosine(a, b): return dot(a, b) / (norm(a) * norm(b) + 1e-12)


if __name__ == "__main__":
    khach_quen  = [0.9, 0.1, 0.0]
    khach_cu    = [0.85, 0.15, 0.05]
    hoa_don     = [0.0, 0.2, 0.95]

    print(f"khách quen vs khách cũ : {cosine(khach_quen, khach_cu):.3f}")
    print(f"khách quen vs hoá đơn  : {cosine(khach_quen, hoa_don):.3f}")
    print(f"vector với chính nó    : {cosine(khach_quen, khach_quen):.3f}")
```

### Phần B — Embedding thật (50')

```powershell
pip install openai numpy
```

`exercises/day05/embed_demo.py`:

```python
"""Ngày 5B: embedding thật + tìm kiếm ngữ nghĩa mini."""
import os, json, hashlib
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

CACHE = Path("exercises/day05/.cache.json")      # cache = tiết kiệm tiền, làm ngay từ đầu
_cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def embed(text: str) -> np.ndarray:
    key = hashlib.sha256((MODEL + text).encode()).hexdigest()
    if key not in _cache:
        r = client.embeddings.create(model=MODEL, input=text)
        _cache[key] = r.data[0].embedding
        CACHE.write_text(json.dumps(_cache), encoding="utf-8")
    return np.array(_cache[key])


def cos(a, b) -> float:
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


KB = [
    "Chính sách hoàn tiền: hoàn 100% nếu huỷ trước 24 giờ.",
    "Gói trị liệu da mặt 10 buổi, hạn sử dụng 6 tháng kể từ ngày mua.",
    "Giờ mở cửa: 9h00 - 20h00 các ngày trong tuần, chủ nhật nghỉ.",
    "Khách hàng có thể chuyển nhượng gói cho người thân, cần báo trước 3 ngày.",
    "Phí giữ chỗ 200.000đ sẽ được trừ vào hoá đơn cuối.",
]


def search(query: str, k: int = 2):
    qv = embed(query)
    scored = [(cos(qv, embed(doc)), doc) for doc in KB]
    return sorted(scored, reverse=True)[:k]


if __name__ == "__main__":
    print("=== Cặp câu — đo độ gần ===")
    pairs = [
        ("đặt lịch hẹn", "book an appointment"),
        ("đặt lịch hẹn", "huỷ lịch hẹn"),
        ("gói còn hiệu lực", "gói đã hết hạn"),
        ("có bảo hành", "không có bảo hành"),      # bẫy phủ định!
        ("giá bao nhiêu", "chi phí thế nào"),
    ]
    for a, b in pairs:
        print(f"  {cos(embed(a), embed(b)):.3f}  |  {a!r} <-> {b!r}")

    print("\n=== Tìm kiếm ngữ nghĩa ===")
    for q in ["tôi huỷ lịch có mất tiền không",
              "cuối tuần có làm việc không",
              "gói của tôi dùng được bao lâu"]:
        print(f"\nHỏi: {q}")
        for score, doc in search(q):
            print(f"  {score:.3f}  {doc}")
```

### Quan sát bắt buộc

1. Cặp **"có bảo hành" vs "không có bảo hành"** điểm bao nhiêu? Đây là bằng chứng của mục 1.5 — ghi vào note.
2. Câu hỏi "tôi huỷ lịch có mất tiền không" tìm đúng tài liệu không? Chú ý: **không có từ nào trùng nhau** mà vẫn tìm ra. Đó là sức mạnh của embedding.
3. Chạy lần 2 — nhanh hơn hẳn nhờ cache. Cache embedding là thói quen bắt buộc.

---

## 4. Bài tập

**Bài 1 — Mở rộng KB.** Thêm 10 câu kiến thức về spa/phòng khám và 10 câu hỏi khách hay hỏi. Đo: bao nhiêu câu hỏi tìm đúng tài liệu ở top-1? Ghi tỉ lệ vào note. Đây là **recall@1** đầu tiên của bạn — Phase 3 sẽ đo chuyên nghiệp hơn.

**Bài 2 — Tìm ngưỡng.** Tạo 10 cặp câu "liên quan" và 10 cặp "không liên quan". Tính điểm trung bình mỗi nhóm. Ngưỡng nào tách được 2 nhóm? So với bảng ở mục 1.2 — giống hay khác?

**Bài 3 — Bẫy số học.** Đo similarity giữa `"gói 5 buổi"` và `"gói 50 buổi"`. Viết 3 câu giải thích vì sao đây là vấn đề nghiêm trọng nếu dùng RAG cho CareDesk-AI, và đề xuất cách xử lý.

---

## 5. Quiz nhớ bài

```powershell
python quiz\quiz.py --day 5
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `similarity.py` tự cài đúng (vector với chính nó = 1.000)
- [ ] `embed_demo.py` chạy, có cache hoạt động
- [ ] Nêu được ≥ 2 giới hạn của embedding **kèm số liệu tự đo**
- [ ] Bài 1 có tỉ lệ recall@1 cụ thể
- [ ] Quiz ≥ 80%
