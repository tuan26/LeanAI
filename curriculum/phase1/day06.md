# NGÀY 6 — Attention

> Phase 1 · 35' lý thuyết — 15' tài liệu — 60' code — 10' note

## 🎯 Mục tiêu

Tự cài self-attention bằng numpy và giải thích được Q, K, V bằng một ví dụ đời thường. Đây là ngày khó nhất tuần 1 — nếu vượt qua, phần còn lại của Phase 1 nhẹ nhàng.

---

## 1. Lý thuyết cốt lõi (35 phút)

### 1.1 Vấn đề attention giải quyết

```
"Chị Lan đã mua gói trị liệu, nhưng chị ấy chưa dùng hết."
                                      ↑
                          "chị ấy" là ai? → cần nhìn lại "Chị Lan"
```

Mỗi token cần **lấy thông tin từ những token liên quan**, bất kể xa gần. Attention là cơ chế làm việc đó.

### 1.2 Q, K, V — ví dụ thư viện

Hình dung bạn vào thư viện:

| Ký hiệu | Tên | Ví dụ thư viện | Trong câu |
|---|---|---|---|
| **Q** (Query) | tôi đang cần gì | "tôi tìm sách về hợp đồng" | "chị ấy" cần biết chỉ ai |
| **K** (Key) | mỗi cuốn tự mô tả mình | nhãn gáy sách | mỗi token quảng cáo "tôi là danh từ chỉ người" |
| **V** (Value) | nội dung thật của cuốn sách | ruột sách | thông tin ngữ nghĩa token mang theo |

Quy trình: so **Q** của tôi với **K** của mọi cuốn → ra điểm khớp → lấy **V** theo tỉ lệ điểm đó.

Cả Q, K, V đều là **phép chiếu tuyến tính từ cùng một vector đầu vào**:
```
Q = X·Wq     K = X·Wk     V = X·Wv
```
Wq, Wk, Wv là tham số học được (nhớ Ngày 2).

### 1.3 Công thức

```
Attention(Q, K, V) = softmax( Q·Kᵀ / √d_k ) · V
                     └───────┬────────┘
                       ma trận trọng số
                     (token i chú ý token j bao nhiêu)
```

Giải thích từng phần:

| Thành phần | Vì sao có |
|---|---|
| `Q·Kᵀ` | điểm khớp giữa mọi cặp token → ma trận n×n |
| `/ √d_k` | chia để giữ phương sai ổn định; không chia thì softmax bão hoà, gradient chết |
| `softmax` | biến điểm thành **tỉ lệ chú ý**, tổng = 1 |
| `· V` | trộn thông tin theo tỉ lệ đó |

### 1.4 Causal mask — vì sao model không "nhìn trộm"

Khi sinh văn bản, token thứ 3 **không được** thấy token thứ 4, 5. Ta cộng `-inf` vào nửa trên ma trận điểm trước khi softmax:

```
        chị    Lan    chưa   dùng
chị   [ 0.9   -inf   -inf   -inf ]
Lan   [ 0.4    0.6   -inf   -inf ]
chưa  [ 0.2    0.3    0.5   -inf ]
dùng  [ 0.1    0.4    0.2    0.3 ]
```

Sau softmax, `-inf` → 0. Đây là chữ "Masked" ở Ngày 3.

### 1.5 Multi-head

Một head chỉ học được một kiểu quan hệ. Chia d_model thành h phần, mỗi phần học riêng rồi ghép lại:

```
head 1: quan hệ ngữ pháp (chủ ngữ ↔ động từ)
head 2: quan hệ đồng tham chiếu ("chị ấy" ↔ "chị Lan")
head 3: quan hệ khoảng cách gần
...ghép lại → W_o → đầu ra
```

### 1.6 Hệ quả tiền bạc: chi phí O(n²)

Ma trận điểm là n×n với n = số token. Gấp đôi context → **gấp 4 lần tính toán attention**.

Đây là lý do:
- prompt dài làm latency tăng phi tuyến,
- nhồi cả tài liệu vào prompt là chiến lược tồi → phải dùng RAG (Phase 3),
- prompt caching tiết kiệm được rất nhiều (Ngày 70).

---

## 2. Tài liệu (15 phút)

| Nguồn | Link | Bắt buộc |
|---|---|---|
| 3Blue1Brown — Attention in transformers | https://www.youtube.com/watch?v=eMlx5fFNoYc | ✅ xem 2 lần |
| Jay Alammar — Illustrated Transformer (phần Self-Attention) | https://jalammar.github.io/illustrated-transformer/ | ✅ |
| Karpathy — Let's build GPT (phần attention, ~0:56:00) | https://www.youtube.com/watch?v=kCc8FmEb1nY | tuỳ chọn |

---

## 3. Thực hành (60 phút)

`exercises/day06/attention.py`:

```python
"""Ngày 6: self-attention từ đầu, thuần numpy."""
import numpy as np

rng = np.random.default_rng(7)


def softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def self_attention(X, Wq, Wk, Wv, causal=True):
    """X: (n_tokens, d_model). Trả về (output, attention_weights)."""
    Q, K, V = X @ Wq, X @ Wk, X @ Wv
    d_k = K.shape[-1]

    scores = Q @ K.T / np.sqrt(d_k)                 # (n, n)

    if causal:
        n = scores.shape[0]
        mask = np.triu(np.ones((n, n)), k=1).astype(bool)
        scores = np.where(mask, -np.inf, scores)

    weights = softmax(scores)                       # mỗi hàng tổng = 1
    return weights @ V, weights


def show_weights(tokens, W):
    print("        " + "".join(f"{t:>8}" for t in tokens))
    for i, t in enumerate(tokens):
        row = "".join(f"{w:>8.2f}" for w in W[i])
        print(f"{t:>8}{row}")


if __name__ == "__main__":
    tokens = ["Chị", "Lan", "chưa", "dùng", "gói"]
    n, d = len(tokens), 8

    X = rng.normal(0, 1, (n, d))
    Wq = rng.normal(0, 0.3, (d, d))
    Wk = rng.normal(0, 0.3, (d, d))
    Wv = rng.normal(0, 0.3, (d, d))

    out, W = self_attention(X, Wq, Wk, Wv, causal=True)

    print("=== Trọng số attention (có mask) ===")
    show_weights(tokens, W)
    print("\nTổng mỗi hàng:", W.sum(axis=1).round(3), "<- phải bằng 1")
    print("Tam giác trên phải bằng 0 (không nhìn tương lai)")

    print("\n=== Không mask ===")
    _, W2 = self_attention(X, Wq, Wk, Wv, causal=False)
    show_weights(tokens, W2)

    print("\n=== Ảnh hưởng của phép chia sqrt(d_k) ===")
    Q, K = X @ Wq, X @ Wk
    for scale, name in ((np.sqrt(d), "có chia √d_k"), (1.0, "KHÔNG chia")):
        w = softmax(Q @ K.T / scale)
        print(f"  {name:>14}: entropy TB = {-(w*np.log(w+1e-9)).sum(1).mean():.3f}")
    print("  entropy thấp = chú ý dồn vào 1 token = gradient nhỏ = khó học")
```

### Thí nghiệm bắt buộc

1. Chạy với `causal=True` và `False`, so sánh tam giác trên.
2. Bỏ phép chia `√d_k` với `d=256` → xem entropy tụt thế nào.
3. Tăng `n` lên 1000 và đo thời gian, rồi 2000 → thời gian gấp mấy lần? Xác nhận O(n²) bằng số liệu thật.

---

## 4. Bài tập

**Bài 1 — Multi-head.** Mở rộng `self_attention` thành `multi_head_attention(X, n_heads)`: chia d_model thành `n_heads` phần, chạy attention song song, concat, nhân `W_o`.
*Tiêu chí:* với `n_heads=1` kết quả phải gần giống hàm cũ.

**Bài 2 — Đo O(n²).** Viết script đo thời gian attention với n = 128, 256, 512, 1024, 2048. Vẽ bảng. Tỉ lệ thời gian có ≈ tỉ lệ n² không?
Từ đó trả lời: *nhồi 50 trang tài liệu vào prompt mỗi lần hỏi — vấn đề là gì?*

**Bài 3 — Giải thích.** Viết `progress/notes/day06.md`: giải thích Q, K, V bằng **một ví dụ khác** ví dụ thư viện (đừng lặp lại của tôi). Ví dụ của bạn phải có đủ 3 vai trò.

---

## 5. Quiz nhớ bài

```powershell
python quiz\quiz.py --day 6
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] `attention.py` chạy, tổng mỗi hàng = 1, tam giác trên = 0
- [ ] Multi-head hoạt động
- [ ] Có bảng số liệu chứng minh O(n²)
- [ ] Giải thích Q/K/V bằng ví dụ riêng
- [ ] Quiz ≥ 80%

> Nếu hôm nay khó: bình thường. Xem lại video 3Blue1Brown lần 2 vào ngày ôn tập (Ngày 7).
