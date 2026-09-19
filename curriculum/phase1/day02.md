# NGÀY 2 — Neural Network

> Phase 1 · 30' lý thuyết — 20' tài liệu — 60' code — 10' note

## 🎯 Mục tiêu

Tự tay viết một neuron và một mạng 2 lớp bằng numpy, **không dùng framework**. Sau hôm nay bạn phải giải thích được: "học" nghĩa là gì, và "tham số" (parameter) của model thực chất là con số gì.

---

## 1. Lý thuyết cốt lõi (30 phút)

### 1.1 Một neuron = 3 phép tính

```
đầu vào x₁ ──w₁──┐
đầu vào x₂ ──w₂──┼──► z = w₁x₁ + w₂x₂ + b ──► a = f(z) ──► đầu ra
đầu vào x₃ ──w₃──┘        (tổ hợp tuyến tính)   (hàm kích hoạt)
```

- **w (weight)**: mức độ quan trọng của từng đầu vào. Đây là thứ model **học được**.
- **b (bias)**: độ lệch, cho phép dịch chuyển ngưỡng.
- **f (activation)**: hàm phi tuyến. Không có nó, xếp 100 lớp cũng chỉ bằng 1 lớp.

> Khi nghe "model 70 tỷ tham số" — đó chính là 70 tỷ con số w và b. Không hơn.

### 1.2 Vì sao cần phi tuyến

Tổ hợp của các hàm tuyến tính vẫn là tuyến tính:
`W₂(W₁x + b₁) + b₂ = (W₂W₁)x + (W₂b₁ + b₂)` — vẫn chỉ là một phép nhân ma trận.

Hàm phi tuyến phổ biến:

| Hàm | Công thức | Dùng khi |
|---|---|---|
| ReLU | `max(0, z)` | mặc định cho lớp ẩn, rẻ và hiệu quả |
| Sigmoid | `1/(1+e⁻ᶻ)` | đầu ra xác suất nhị phân |
| Softmax | `eᶻⁱ/Σeᶻʲ` | **đầu ra LLM** — biến điểm số thành xác suất token |
| GELU | ~ReLU mượt | dùng trong Transformer thực tế |

Softmax là hàm bạn sẽ gặp lại ở Ngày 6 và Ngày 9. Nhớ nó.

### 1.3 "Học" là gì

Vòng lặp 4 bước, lặp hàng triệu lần:

```
1. FORWARD   : đưa dữ liệu qua mạng → dự đoán ŷ
2. LOSS      : đo sai lệch giữa ŷ và y thật  (vd: cross-entropy)
3. BACKWARD  : tính đạo hàm loss theo từng w  (backpropagation)
4. UPDATE    : w ← w − lr × ∂loss/∂w          (gradient descent)
```

**Learning rate (lr)** quá lớn → nhảy qua đáy, loss dao động. Quá nhỏ → học mãi không xong.

### 1.4 Liên hệ tới LLM

LLM chính là mạng neuron rất sâu, với:
- đầu vào = dãy token (Ngày 4)
- lớp giữa = khối Transformer (Ngày 3, 6)
- đầu ra = softmax trên **toàn bộ từ vựng** (~100k–200k token)

Khi bạn gọi API và nhận một chữ, thực chất model đã tính xác suất cho *cả trăm nghìn* token rồi chọn một.

---

## 2. Tài liệu (20 phút)

| Nguồn | Link | Bắt buộc |
|---|---|---|
| 3Blue1Brown — Neural networks Ch.1 (xem hết) | https://www.youtube.com/watch?v=aircAruvnKk | ✅ |
| 3Blue1Brown — Gradient descent Ch.2 | https://www.youtube.com/watch?v=IHZwWFHWa-w | ✅ |
| Karpathy — micrograd (chỉ xem 0–25') | https://www.youtube.com/watch?v=VMj-3S1tku0 | tuỳ chọn, rất đáng |

---

## 3. Thực hành (60 phút)

`exercises/day02/neuron.py`:

```python
"""Ngày 2: neuron và mạng 2 lớp, thuần numpy."""
import numpy as np

rng = np.random.default_rng(42)


def relu(z):    return np.maximum(0, z)
def sigmoid(z): return 1 / (1 + np.exp(-z))

def softmax(z):
    z = z - np.max(z)          # trừ max để tránh tràn số — thủ thuật bắt buộc
    e = np.exp(z)
    return e / e.sum()


def neuron(x, w, b, f=relu):
    return f(np.dot(x, w) + b)


class TinyNet:
    """2 đầu vào -> 4 neuron ẩn -> 1 đầu ra. Học bằng gradient descent thủ công."""

    def __init__(self):
        self.W1 = rng.normal(0, 0.5, (2, 4))
        self.b1 = np.zeros(4)
        self.W2 = rng.normal(0, 0.5, (4, 1))
        self.b2 = np.zeros(1)

    def forward(self, X):
        self.Z1 = X @ self.W1 + self.b1
        self.A1 = relu(self.Z1)
        self.Z2 = self.A1 @ self.W2 + self.b2
        return sigmoid(self.Z2)

    def train(self, X, y, epochs=3000, lr=0.1):
        n = len(X)
        for ep in range(epochs):
            out = self.forward(X)
            loss = -np.mean(y * np.log(out + 1e-9) + (1 - y) * np.log(1 - out + 1e-9))

            dZ2 = (out - y) / n                      # đạo hàm của BCE + sigmoid
            dW2 = self.A1.T @ dZ2
            db2 = dZ2.sum(axis=0)
            dA1 = dZ2 @ self.W2.T
            dZ1 = dA1 * (self.Z1 > 0)                # đạo hàm ReLU
            dW1 = X.T @ dZ1
            db1 = dZ1.sum(axis=0)

            for p, g in ((self.W1, dW1), (self.b1, db1), (self.W2, dW2), (self.b2, db2)):
                p -= lr * g

            if ep % 500 == 0:
                print(f"epoch {ep:>4}  loss {loss:.4f}")


if __name__ == "__main__":
    print("softmax([2,1,0.1]) =", softmax(np.array([2.0, 1.0, 0.1])).round(3))

    # XOR: bài toán KHÔNG giải được bằng 1 lớp tuyến tính
    X = np.array([[0., 0.], [0., 1.], [1., 0.], [1., 1.]])
    y = np.array([[0.], [1.], [1.], [0.]])

    net = TinyNet()
    net.train(X, y)
    print("\nDự đoán XOR:", net.forward(X).round(3).ravel())
    print("Số tham số:", net.W1.size + net.b1.size + net.W2.size + net.b2.size)
```

### Thí nghiệm bắt buộc

1. Đổi `relu` thành hàm đồng nhất (`lambda z: z`) → mạng **không** học được XOR. Đó là bằng chứng của mục 1.2.
2. Đổi `lr=5.0` → quan sát loss nổ tung.
3. Đổi `lr=0.001` → quan sát loss gần như đứng yên.

Ghi lại cả 3 kết quả vào note. Đây là trực giác bạn sẽ dùng khi chỉnh temperature (Ngày 9).

---

## 4. Bài tập

**Bài 1.** Viết hàm `count_params(layers: list[int]) -> int` tính số tham số của mạng fully-connected.
Kiểm tra: `count_params([2,4,1])` phải bằng đúng con số mạng trên in ra.

**Bài 2.** Tự cài `softmax` *không dùng* trick trừ max, rồi gọi với `np.array([1000., 1001.])`. Giải thích lỗi nhận được và vì sao trick đó cần thiết. (Gợi ý: đây là lỗi thật xảy ra trong production.)

**Bài 3.** Note `progress/notes/day02.md` trả lời: *"Nếu model có 70 tỷ tham số, chính xác thì 70 tỷ con số đó là gì và chúng được quyết định lúc nào?"*

---

## 5. Quiz nhớ bài

```powershell
python quiz\quiz.py --day 2
python quiz\quiz.py --review      # ôn lại Ngày 1
```

---

## 6. PASS/FAIL

- [ ] `neuron.py` chạy, XOR dự đoán đúng (≈0, ≈1, ≈1, ≈0)
- [ ] Chứng minh được mạng tuyến tính thất bại với XOR
- [ ] Giải thích được overflow của softmax
- [ ] Quiz ngày 2 ≥ 80% **và** review ngày 1 ≥ 80%
