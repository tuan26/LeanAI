<#
  Deploy LeanAI lên Fly.io — chạy được nhiều lần, không hỏng gì nếu chạy lại.

      .\deploy-fly.ps1                      # deploy (tạo app + volume nếu chưa có)
      .\deploy-fly.ps1 -AppName leanai-abc  # đặt tên app khác
      .\deploy-fly.ps1 -Backup              # tải tiến trình học từ server về máy

  Yêu cầu: đã chạy `fly auth login` một lần.
#>
param(
  [string]$AppName = "",
  [string]$Region  = "sin",
  [int]$VolumeGb   = 1,
  [switch]$Backup
)

$ErrorActionPreference = "Stop"
$fly = "$env:USERPROFILE\.fly\bin\flyctl.exe"
if (-not (Test-Path $fly)) { $fly = (Get-Command flyctl -ErrorAction SilentlyContinue).Source }
if (-not $fly) { throw "Không tìm thấy flyctl. Cài bằng: iwr https://fly.io/install.ps1 -useb | iex" }

function Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }

# ---------------------------------------------------------------- tên app
if (-not $AppName) {
  $AppName = (Select-String -Path fly.toml -Pattern '^app\s*=\s*"(.+)"').Matches.Groups[1].Value
}
Write-Host "App    : $AppName"
Write-Host "Region : $Region"

# ---------------------------------------------------------------- đăng nhập
Step "Kiểm tra đăng nhập"
$who = & $fly auth whoami 2>&1
if ($LASTEXITCODE -ne 0) { throw "Chưa đăng nhập. Chạy: $fly auth login" }
Write-Host "Đang đăng nhập với: $who"

# ---------------------------------------------------------------- backup
if ($Backup) {
  Step "Tải tiến trình học về máy"
  New-Item -ItemType Directory -Force backups | Out-Null
  $stamp = Get-Date -Format "yyyyMMdd-HHmm"
  & $fly ssh console -a $AppName -C "tar czf - -C /data ." > "backups\leanai-$stamp.tgz"
  Write-Host "Đã lưu backups\leanai-$stamp.tgz" -ForegroundColor Green
  exit 0
}

# ---------------------------------------------------------------- tạo app
Step "Tạo app nếu chưa có"
& $fly status -a $AppName *> $null
if ($LASTEXITCODE -ne 0) {
  & $fly apps create $AppName --org personal
  if ($LASTEXITCODE -ne 0) { throw "Không tạo được app. Tên có thể đã bị người khác dùng — chạy lại với -AppName khác." }
} else { Write-Host "App đã tồn tại." }

# ---------------------------------------------------------------- volume
Step "Tạo volume giữ tiến trình"
$vols = & $fly volumes list -a $AppName 2>&1 | Out-String
if ($vols -notmatch "leanai_data") {
  & $fly volumes create leanai_data --size $VolumeGb --region $Region -a $AppName --yes
  Write-Host "Đã tạo volume $VolumeGb GB." -ForegroundColor Green
} else { Write-Host "Volume đã tồn tại — tiến trình cũ được giữ nguyên." }

# ---------------------------------------------------------------- mật khẩu
Step "Mật khẩu truy cập"
$secrets = & $fly secrets list -a $AppName 2>&1 | Out-String
if ($secrets -notmatch "LEANAI_PASS") {
  Write-Host "App chưa có mật khẩu -> sẽ chạy CHẾ ĐỘ CHỈ ĐỌC (xem được bài, không đánh dấu được)."
  $u = Read-Host "Tên đăng nhập (Enter để bỏ qua, giữ chế độ chỉ đọc)"
  if ($u) {
    $p = Read-Host "Mật khẩu" -AsSecureString
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
             [Runtime.InteropServices.Marshal]::SecureStringToBSTR($p))
    if ($plain.Length -lt 10) { throw "Mật khẩu quá ngắn — dùng ít nhất 10 ký tự." }
    & $fly secrets set "LEANAI_USER=$u" "LEANAI_PASS=$plain" -a $AppName --stage
    Write-Host "Đã đặt mật khẩu." -ForegroundColor Green
  }
} else { Write-Host "Đã có mật khẩu từ trước." }

# ---------------------------------------------------------------- deploy
Step "Deploy"
& $fly deploy -a $AppName --ha=false
if ($LASTEXITCODE -ne 0) { throw "Deploy thất bại — xem log ở trên." }

# ---------------------------------------------------------------- kiểm tra
Step "Kiểm tra sau deploy"
$url = "https://$AppName.fly.dev"
Start-Sleep -Seconds 6
try {
  $h = Invoke-RestMethod "$url/healthz" -TimeoutSec 30
  Write-Host "healthz : lessons=$($h.lessons) questions=$($h.questions) auth=$($h.auth) read_only=$($h.read_only)"
  if ($h.lessons -ne 90)    { Write-Warning "Thiếu bài học! curriculum/ chưa vào được image." }
  if ($h.questions -ne 324) { Write-Warning "Thiếu câu quiz! quiz/bank/ chưa vào được image." }
  if ($h.read_only)         { Write-Warning "Đang CHỈ ĐỌC — đặt mật khẩu để đánh dấu được tiến trình." }
} catch { Write-Warning "Chưa gọi được /healthz: $_" }

Write-Host "`nXong: $url" -ForegroundColor Green
Write-Host "Sao lưu tiến trình : .\deploy-fly.ps1 -Backup"
Write-Host "Xem log            : $fly logs -a $AppName"
Write-Host "Tắt app            : $fly scale count 0 -a $AppName"
