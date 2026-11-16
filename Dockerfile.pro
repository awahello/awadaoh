# syntax=docker/dockerfile:1
# PRO 版运行镜像：使用已打过补丁的二进制 + 自己的前端包
# 构建前先执行 tools/build-pro.sh 生成 ./pro/ 目录
FROM alpine:3.19

LABEL org.opencontainers.image.title="AKKdaoh PRO" \
      org.opencontainers.image.source="https://github.com/awahello/akkdaoh"

WORKDIR /app

COPY ./pro/web /app/web
COPY ./pro/akkdaoh /app/akkdaoh

ENV TZ=Asia/Shanghai

EXPOSE 3002

RUN apk add --no-cache bash ca-certificates su-exec tzdata curl \
    && chmod +x ./akkdaoh \
    && ./akkdaoh -config

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:3002/ || exit 1

CMD ["./akkdaoh"]
