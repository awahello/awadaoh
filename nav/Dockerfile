# syntax=docker/dockerfile:1
# AKKdaoh Nav · 极简导航站
#
# 构建：
#   docker build -f nav/Dockerfile -t akkdaoh-nav .
# 运行：
#   docker run -d --name nav -p 8080:8080 -v $(pwd)/data:/app/data akkdaoh-nav
#
# 前台 http://IP:8080/      后台 http://IP:8080/admin

FROM python:3.12-alpine

LABEL org.opencontainers.image.title="AKKdaoh Nav" \
      org.opencontainers.image.description="极简自托管导航站：打开即用，后台改配置，支持导入 Chrome 书签" \
      org.opencontainers.image.source="https://github.com/awahello/akkdaoh"

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DATA_DIR=/app/data \
    TZ=Asia/Shanghai

COPY server.py /app/server.py
COPY static /app/static

RUN mkdir -p /app/data \
    && apk add --no-cache tzdata curl \
    && adduser -D -u 10001 nav \
    && chown -R nav:nav /app

USER nav

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=8s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/api/health || exit 1

CMD ["python3", "/app/server.py"]
