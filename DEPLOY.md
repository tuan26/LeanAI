# DEPLOY — chạy LeanAI ngoài máy cá nhân

> App này chứa **tiến trình học cá nhân** của bạn và cho phép ghi (đánh dấu ngày xong,
> chấm quiz). Trước khi mở ra ngoài, đọc phần An ninh.

## An ninh — đọc trước

| Tình huống | Hành vi của app |
|---|---|
| `HOST=127.0.0.1` (mặc định, chạy local) | không cần mật khẩu, ghi bình thường |
| `HOST=0.0.0.0` + **không** đặt mật khẩu | tự chuyển **CHẾ ĐỘ CHỈ ĐỌC** — mọi POST bị chặn 403 |
| `HOST=0.0.0.0` + `LEANAI_USER`/`LEANAI_PASS` | HTTP Basic auth, ghi bình thường |

Nghĩa là: lỡ deploy mà quên mật khẩu thì người lạ **không phá được** tiến trình của bạn.

Đặt mật khẩu mạnh, không dùng lại mật khẩu ở nơi khác. Basic auth chỉ an toàn khi
chạy sau HTTPS — mọi nền tảng dưới đây đều cấp HTTPS sẵn.

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `HOST` | `127.0.0.1` | `0.0.0.0` khi chạy trong container |
| `PORT` | `8080` | nền tảng cloud thường tự tiêm biến này |
| `LEANAI_USER` / `LEANAI_PASS` | rỗng | bật xác thực |
| `LEANAI_DATA_DIR` | thư mục repo | trỏ vào volume để giữ tiến trình |
| `LEANAI_READ_ONLY` | tự suy ra | ép chế độ chỉ đọc |

---

## Cách 1 — Docker trên máy (đã kiểm chứng)

```bash
docker compose up -d --build
# mở http://127.0.0.1:8080
```

Dữ liệu nằm trong volume `leanai-data`, không mất khi container restart.
`curriculum/` và `quiz/bank/` được mount read-only nên sửa bài học trên máy là thấy ngay.

Sao lưu / khôi phục tiến trình:

```bash
docker run --rm -v leanai-data:/d -v "$PWD":/b alpine tar czf /b/leanai-backup.tgz -C /d .
docker run --rm -v leanai-data:/d -v "$PWD":/b alpine tar xzf /b/leanai-backup.tgz -C /d
```

## Cách 2 — Học trên điện thoại trong cùng WiFi (rẻ nhất, không cần tài khoản)

Sửa `docker-compose.yml`, đổi `"127.0.0.1:8080:8080"` thành `"8080:8080"`, rồi:

```bash
LEANAI_USER=tuan LEANAI_PASS=<mật-khẩu-mạnh> docker compose up -d
ipconfig     # lấy IPv4 của máy, ví dụ 192.168.1.12
```

Trên điện thoại mở `http://192.168.1.12:8080`. Nhớ mở cổng 8080 trong Windows Firewall.

> Không đặt mật khẩu thì điện thoại vẫn xem được bài học nhưng không đánh dấu được —
> đó là chế độ chỉ đọc đang bảo vệ bạn.

## Cách 3 — Fly.io (có free tier, giữ được volume)

```bash
fly launch --no-deploy --name leanai-<tên-bạn>
fly volumes create leanai_data --size 1 --region sin
fly secrets set LEANAI_USER=tuan LEANAI_PASS=<mật-khẩu-mạnh>
fly deploy
```

`fly.toml` cần có:

```toml
[env]
  HOST = "0.0.0.0"
  PORT = "8080"
  LEANAI_DATA_DIR = "/data"

[[mounts]]
  source = "leanai_data"
  destination = "/data"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "stop"
  min_machines_running = 0
```

`auto_stop_machines` cho máy ngủ khi không dùng — gần như không tốn tiền.

## Cách 4 — Railway / Render

Cả hai đều tự nhận `Dockerfile`.

1. Kết nối repo GitHub
2. Thêm biến môi trường: `HOST=0.0.0.0`, `LEANAI_USER`, `LEANAI_PASS`, `LEANAI_DATA_DIR=/data`
3. **Gắn persistent disk** vào `/data`

> ⚠️ Không gắn disk thì tiến trình học **mất mỗi lần deploy lại**. Free tier của Render
> không có disk — khi đó nên dùng Fly.io hoặc chấp nhận chế độ chỉ đọc.

## Cách 5 — Tailscale (riêng tư nhất)

Cài Tailscale trên máy và điện thoại, chạy `docker compose up -d` với `HOST=0.0.0.0`,
rồi vào bằng IP Tailscale. App không lộ ra internet công cộng mà vẫn dùng được mọi nơi.

---

## Kiểm tra sau khi deploy

```bash
curl -u user:pass https://<domain>/healthz
# {"ok":true,"lessons":90,"questions":324,"read_only":false,"auth":true}

curl -o /dev/null -w "%{http_code}\n" https://<domain>/api/overview      # 401
curl -X POST https://<domain>/api/day/1/status -d '{"status":"pass"}'    # 401 hoặc 403
```

`lessons` phải bằng 90 và `questions` bằng 324. Nếu ít hơn là `curriculum/` hoặc
`quiz/bank/` chưa vào được image.

## Lưu ý về đồng bộ

Deploy lên cloud thì tiến trình nằm **trên server**, còn `quiz/quiz.py` và `track.py`
trên máy bạn đọc file local — hai bên sẽ lệch nhau. Chọn một trong hai:

- Học trên web, thỉnh thoảng tải `/data` về (lệnh backup ở Cách 1)
- Hoặc chỉ dùng Docker local + LAN, giữ một nguồn dữ liệu duy nhất
