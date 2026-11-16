# syntax=docker/dockerfile:1
# ── Awadaoh PRO 运行镜像 ─────────────────────────────────────────
# 物料由 tools/build-pro.sh 生成：
#   pro/web               已注入导航站主题的前端包（与后端同版本）
#   pro/<arch>/awadaoh    ProIsExpired 已恒 false 的后端二进制
#
# 构建：
#   docker buildx build --platform linux/amd64,linux/arm64 \
#     -f Dockerfile.pro -t awahello/awadaoh:latest --push .
#
# 单架构本地构建：
#   ./tools/build-pro.sh /path/to/sun-panel_vX_linux_arm64 pro/amd64
#   docker build -f Dockerfile.pro -t awadaoh:pro .
FROM alpine:3.19

# buildx 自动注入目标架构。故意不给默认值：
# 万一没被注入（比如有人用老版本 docker build 且没开 BuildKit），
# 宁可在这里报 "TARGETARCH 为空" 也不要默默按 amd64 打包，
# 打出一个标签写着 arm64、里面躺着 amd64 二进制的镜像。
ARG TARGETARCH

LABEL org.opencontainers.image.title="Awadaoh" \
      org.opencontainers.image.description="自托管导航面板 / NAS 首页 / 浏览器起始页（PRO 全功能）" \
      org.opencontainers.image.source="https://github.com/awahello/awadaoh" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY ./pro/web /app/web
COPY ./pro/${TARGETARCH}/awadaoh /app/awadaoh
# 端口写死 3055：上游二进制内嵌的 conf.example.ini 是 3002，
# 只靠 RUN ./awadaoh -config 生成会回到 3002，所以这里直接带一份 conf/conf.ini
# （tools/build-pro.sh 会把它写进 pro/<arch>/conf/conf.ini）
COPY ./pro/${TARGETARCH}/conf /app/conf
# 入口脚本用它兜底：宿主机 ./conf 挂进来是空目录时，先把这份模板拷进去
COPY ./service/assets/conf.example.ini /app/conf.example.ini
COPY ./docker/pro-entrypoint.sh /app/docker-entrypoint.sh

ENV TZ=Asia/Shanghai

EXPOSE 3055

# 架构守卫 + 运行期准备。
# 这个 RUN 是本 Dockerfile 唯一能真正「跑起来」二进制的机会，所以先把 ELF 头核了：
#   e_machine 偏移 18 两个字节，小端：amd64=3e00  arm64=b700
# 对不上就直接 fail build。没有这一步，buildx 会开开心心把错架构的文件打成
# linux/arm64 镜像，用户 pull 下来才 exec format error（就是这次的故障）。
RUN set -eu; \
    case "${TARGETARCH:-}" in \
      amd64) want=3e00 ;; \
      arm64) want=b700 ;; \
      "") echo "!! TARGETARCH 未注入，无法确定该装哪个二进制"; exit 1 ;; \
      *) echo "!! 不支持的 TARGETARCH=${TARGETARCH}"; exit 1 ;; \
    esac; \
    got="$(od -An -tx1 -j18 -N2 /app/awadaoh | tr -d ' \n')"; \
    echo "架构守卫: TARGETARCH=${TARGETARCH} ELF e_machine=${got} 期望=${want}"; \
    if [ "$got" != "$want" ]; then \
      echo "!! /app/awadaoh 架构不符：这个镜像打出来必然 exec format error"; \
      echo "!! 检查 pro/${TARGETARCH}/awadaoh 的来源包，用 python3 tools/elfarch.py 复核"; \
      exit 1; \
    fi; \
    apk add --no-cache bash ca-certificates su-exec tzdata curl; \
    chmod +x ./awadaoh ./docker-entrypoint.sh; \
    ( [ -f /app/conf/conf.ini ] \
        && sed -i 's/^[[:space:]]*http_port.*/http_port=3055/' /app/conf/conf.ini \
        || printf '[base]\nhttp_port=3055\n' > /app/conf/conf.ini ); \
    grep -q '^http_port=3055' /app/conf/conf.ini

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:3055/ || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
