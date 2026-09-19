# SETUP — Môi trường học (làm 1 lần, ngày 0)

Thời gian: 45–60 phút. Làm xong mới bắt đầu Ngày 1.

## 1. Python 3.11+

```powershell
python --version        # cần >= 3.11
```

Chưa có → tải tại python.org, nhớ tick **Add Python to PATH**.

## 2. Virtual env + thư viện

```powershell
cd E:\testAI\LeanAI
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Nếu PowerShell chặn script:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## 3. API key

Chọn **1 provider chính** (khuyên dùng Anthropic Claude) + 1 provider dự phòng.

```powershell
copy .env.example .env
notepad .env
```

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...          # tuỳ chọn, dùng cho embedding
```

**Ngân sách:** nạp trước 20–30 USD cho cả 90 ngày là đủ nếu bạn theo đúng phần "cost discipline" ở Phase 5.
Không commit file `.env`. Đã có trong `.gitignore`.

## 4. Kiểm tra

```powershell
python quiz\quiz.py --doctor
```

Kết quả mong đợi:
```
[ok] python 3.13
[ok] .env found
[ok] ANTHROPIC_API_KEY set
[ok] quiz bank: 90 days
```

## 5. Công cụ nên có

| Công cụ | Dùng để | Bắt buộc |
|---|---|---|
| VS Code | editor | ✅ |
| Git | version control mỗi ngày | ✅ |
| Docker Desktop | Postgres + Qdrant từ Phase 3 | Phase 3 |
| Postman / Thunder Client | test API | nên có |
| Node.js 20+ | Next.js ở Phase 6 | Phase 6 |

## 6. Quy ước làm việc mỗi ngày

```powershell
git checkout -b day-01
# ... học và code ...
git add .
git commit -m "day 01: AI vs ML vs DL vs LLM + note"
git checkout main; git merge day-01
```

Mục tiêu: sau 90 ngày bạn có **90 commit** — đó là bằng chứng học thật.

## 7. Chi phí dự kiến

| Khoản | Ước tính |
|---|---|
| LLM API (90 ngày) | 20–30 USD |
| Embedding | 2–5 USD |
| Vector DB (Qdrant local qua Docker) | 0 |
| Postgres (local/Supabase free) | 0 |
| Deploy (Vercel + Railway free tier) | 0–5 USD |
| **Tổng** | **~25–40 USD** |
