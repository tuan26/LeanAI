# NGÀY 3 — Transformer

> Phase 1 · 40' lý thuyết — 20' tài liệu — 50' vẽ + code — 10' note

## 🎯 Mục tiêu

Vẽ được sơ đồ Transformer **từ trí nhớ** và giải thích từng khối làm gì. Hôm nay nặng lý thuyết — ngày mai (tokenization) và ngày 6 (attention) sẽ lấp đầy chi tiết.

---

## 1. Lý thuyết cốt lõi (40 phút)

### 1.1 Vì sao Transformer thắng RNN

| | RNN/LSTM | Transformer |
|---|---|---|
| Xử lý chuỗi | tuần tự, từng token | **song song** toàn bộ chuỗi |
| Phụ thuộc xa | mờ dần theo khoảng cách | truy cập trực tiếp mọi vị trí |
| Huấn luyện trên GPU | kém hiệu quả | tận dụng tối đa |

Một câu: **Transformer đổi bộ nhớ lấy khả năng song song hoá** — và đó là thứ cho phép scale lên nghìn tỷ token.

### 1.2 Sơ đồ khối (decoder-only — kiến trúc của GPT/Claude)

```
                  Token IDs  [18, 442, 9, ...]
                        │
                ┌───────▼────────┐
                │ Token Embedding│  mỗi ID → vector d chiều
                └───────┬────────┘
                        │  + Positional Encoding  (thêm thông tin thứ tự)
                        ▼
        ╔═══════════════════════════════════╗
        ║   TRANSFORMER BLOCK  (× N lớp)    ║
        ║                                   ║
        ║   ┌─────────────────────────┐     ║
        ║   │ LayerNorm               │     ║
        ║   └──────────┬──────────────┘     ║
        ║   ┌──────────▼──────────────┐     ║
        ║   │ Masked Multi-Head       │     ║
        ║   │ Self-Attention          │     ║  ← "token nào nên nhìn token nào"
        ║   └──────────┬──────────────┘     ║
        ║        (+) ◄─┴── residual          ║
        ║   ┌──────────▼──────────────┐     ║
        ║   │ LayerNorm               │     ║
        ║   └──────────┬──────────────┘     ║
        ║   ┌──────────▼──────────────┐     ║
        ║   │ Feed-Forward (MLP)      │     ║  ← "xử lý thông tin đã thu thập"
        ║   └──────────┬──────────────┘     ║
        ║        (+) ◄─┴── residual          ║
        ╚═══════════════╤═══════════════════╝
                        ▼
                ┌───────────────┐
                │ LayerNorm     │
                └───────┬───────┘
                ┌───────▼───────┐
                │ Linear → vocab│  d chiều → ~128.000 điểm số
                └───────┬───────┘
                ┌───────▼───────┐
                │   Softmax     │  → xác suất từng token
                └───────┬───────┘
                        ▼
                 Sampling (Ngày 9) → 1 token
                        │
                        └──── nối vào input, lặp lại ────┐
                                                          ▲
```

### 1.3 Vai trò từng khối — thuộc lòng bảng này

| Khối | Làm gì | Bỏ đi thì sao |
|---|---|---|
| Token Embedding | biến ID rời rạc thành vector có ngữ nghĩa | model không hiểu gì, chỉ thấy số |
| Positional Encoding | thêm thông tin *vị trí* | "chó cắn người" = "người cắn chó" |
| Self-Attention | cho token trộn thông tin với nhau theo ngữ cảnh | mỗi token cô lập, mất ngữ cảnh |
| Masked | chặn nhìn token tương lai | model gian lận khi train, vô dụng khi sinh |
| Multi-Head | nhiều "góc nhìn" quan hệ song song | chỉ học được một kiểu quan hệ |
| Feed-Forward | nơi lưu phần lớn **kiến thức** (2/3 tham số) | không có chỗ chứa tri thức |
| Residual (+) | đường tắt cho gradient | mạng sâu không train nổi |
| LayerNorm | ổn định phân phối số | loss nổ / phân kỳ |

### 1.4 Ba con số quyết định kích thước model

```
d_model   : chiều của vector (vd 4096)
n_layers  : số khối Transformer xếp chồng (vd 32)
n_heads   : số đầu attention (vd 32)
```

Tham số ≈ `12 × n_layers × d_model²`. Thử tính cho `n_layers=32, d_model=4096` → ~6.4 tỷ. Bạn vừa ước lượng được kích thước model.

### 1.5 Điều quan trọng nhất cho công việc của bạn

Mỗi token sinh ra phải chạy qua **toàn bộ** N lớp. Điều này giải thích:
- vì sao **output token đắt hơn input token** (thường 3–5×),
- vì sao **latency tỉ lệ với số token sinh ra**, không phải độ dài câu hỏi,
- vì sao ép model trả lời ngắn gọn là cách tối ưu chi phí rẻ nhất (Ngày 70).

---

## 2. Tài liệu (20 phút)

| Nguồn | Link | Bắt buộc |
|---|---|---|
| Jay Alammar — The Illustrated Transformer | https://jalammar.github.io/illustrated-transformer/ | ✅ đọc kỹ phần hình |
| 3Blue1Brown — But what is a GPT? | https://www.youtube.com/watch?v=wjZofJX0v4M | ✅ |
| Attention Is All You Need (bản gốc) | https://arxiv.org/abs/1706.03762 | đọc abstract + Figure 1 |

---

## 3. Thực hành (50 phút)

### Bước 1 — Vẽ tay (25 phút, KHÔNG nhìn tài liệu)

Lấy giấy A4. Vẽ lại sơ đồ mục 1.2 từ trí nhớ. Chụp ảnh lưu vào `progress/notes/day03-transformer.jpg`.
Vẽ xong mới mở lại file này đối chiếu. Thiếu khối nào → khoanh đỏ, đó là chỗ bạn chưa hiểu.

### Bước 2 — Ước lượng kích thước model (25 phút)

`exercises/day03/model_size.py`:

```python
"""Ngày 3: ước lượng tham số, bộ nhớ và chi phí của một Transformer."""

def transformer_params(n_layers: int, d_model: int, vocab: int = 128_000,
                       d_ff_mult: int = 4) -> dict:
    emb = vocab * d_model                      # token embedding
    attn_per_layer = 4 * d_model * d_model     # Q, K, V, O
    ffn_per_layer = 2 * d_ff_mult * d_model * d_model
    per_layer = attn_per_layer + ffn_per_layer
    total = emb + n_layers * per_layer
    return {
        "embedding": emb,
        "attention_total": n_layers * attn_per_layer,
        "ffn_total": n_layers * ffn_per_layer,
        "total": total,
        "ffn_share": n_layers * ffn_per_layer / total,
    }


def memory_gb(params: int, bytes_per_param: int = 2) -> float:
    """fp16 = 2 byte/tham số. int8 = 1, int4 = 0.5."""
    return params * bytes_per_param / 1e9


if __name__ == "__main__":
    for name, (L, d) in {
        "tiny  (~120M)": (12, 768),
        "medium(~7B)":   (32, 4096),
        "large (~70B)":  (80, 8192),
    }.items():
        p = transformer_params(L, d)
        print(f"{name}: {p['total']/1e9:.1f}B tham số | "
              f"FFN chiếm {p['ffn_share']:.0%} | "
              f"fp16 cần {memory_gb(p['total']):.0f} GB VRAM")
```

Quan sát: **FFN chiếm ~2/3 tham số**. Kiến thức của model nằm ở đó, không nằm ở attention.

---

## 4. Bài tập

**Bài 1.** Giải thích bằng lời (không công thức) vì sao **residual connection** giúp train mạng 80 lớp. Viết ≤ 5 câu.

**Bài 2.** Model 70B chạy fp16 cần bao nhiêu GB? Card RTX 4090 có 24GB — bạn cần bao nhiêu card? Nếu lượng tử hoá xuống int4 thì sao? (Dùng `memory_gb`.)
→ Đây là lý do bạn **thuê API thay vì tự host** trong 90 ngày này.

**Bài 3.** Trong `progress/notes/day03.md`, điền bảng: mỗi khối Transformer — "làm gì" + "bỏ đi thì hỏng gì", viết bằng lời của bạn.

---

## 5. Quiz nhớ bài

```powershell
python quiz\quiz.py --day 3
python quiz\quiz.py --review
```

---

## 6. PASS/FAIL

- [ ] Vẽ lại sơ đồ từ trí nhớ, thiếu ≤ 2 khối
- [ ] Giải thích được cả 8 khối trong bảng 1.3
- [ ] Chạy `model_size.py`, trả lời được Bài 2
- [ ] Quiz ≥ 80%
