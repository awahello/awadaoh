# syntax=docker/dockerfile:1
# ── AKKdaoh PRO 运行镜像 ─────────────────────────────────────────
# 物料由 tools/build-pro.sh 生成：
#   pro/web               已注入导航站主题的前端包（与后端同版本）
#   pro/<arch>/akkdaoh    ProIsExpired 已恒 false 的后端二进制
#
# 构建：
#   docker buildx build --platform linux/amd64,linux/arm64 \
#     -f Dockerfile.pro -t awahello/akkdaoh:latest --push .
#
# 单架构本地构建：
#   ./tools/build-pro.sh /path/to/sun-panel_vX_linux_arm64 pro/amd64
#   docker build -f Dockerfile.pro -t akkdaoh:pro .
FROM alpine:3.19

# buildx 自动注入目标架构，用于挑选对应二进制
ARG TARGETARCH=amd64

LABEL org.opencontainers.image.title="AKKdaoh" \
      org.opencontainers.image.description="自托管导航面板 / NAS 首页 / 浏览器起始页（PRO 全功能）" \
      org.opencontainers.image.source="https://github.com/awahello/akkdaoh" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY ./pro/web /app/web
COPY ./pro/${TARGETARCH}/akkdaoh /app/akkdaoh

ENV TZ=Asia/Shanghai

EXPOSE 3002

RUN apk add --no-cache bash ca-certificates su-exec tzdata curl \
    && chmod +x ./akkdaoh \
    && (./akkdaoh -config || true)

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:3002/ || exit 1

CMD ["./akkdaoh"]
