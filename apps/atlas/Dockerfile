# Atlas — build الـfrontend ثم صورة تشغيل واحدة تخدم API + SPA
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=web /web/dist ./static

ENV ATLAS_STATIC_DIR=/app/static \
    ATLAS_DATABASE_URL=sqlite:////data/atlas.db \
    ATLAS_ENV=production

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 3456

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:3456/api/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3456", "--proxy-headers", "--forwarded-allow-ips", "*"]
