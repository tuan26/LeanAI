FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    LEANAI_DATA_DIR=/data

WORKDIR /app

# Chỉ cài thư viện web app cần — không kéo cả stack của bài học
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# Nội dung học + code app
COPY curriculum/ ./curriculum/
COPY quiz/bank/ ./quiz/bank/
COPY webapp/ ./webapp/

# Tiến trình học nằm ở volume để không mất khi container khởi động lại
VOLUME ["/data"]
RUN mkdir -p /data && useradd -m -u 10001 leanai && chown -R leanai /data /app
USER leanai

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,os,sys; \
    sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",8080)}/healthz', timeout=4).status==200 else 1)"

CMD ["python", "-m", "webapp.server"]
