# syntax=docker/dockerfile:1

# ══════════════════════════════════════════════════════════════════════════
#  Awadaoh 全量镜像 —— 前后端都从本仓库源码构建
#
#    前端  src/       → dist/     node 20 + vite
#    后端  service/   → awadaoh   golang 1.21 + cgo（mattn/go-sqlite3 要 cgo）
#    资源  service/assets/* 用 //go:embed 烘进二进制，运行时不依赖磁盘路径
#
#  和 Dockerfile.pro 的区别：
#    .pro 那个 COPY 的是 pro/ 里的上游预编译二进制 + 上游预编译前端包，
#    src/ 与 service/ 从来没参与打包 —— 所以界面永远是上游那套登录页，
#    分类三态、内网打码、前台无登录这些融合改动一个都进不去。
#    这个 Dockerfile 才是「代码级真融合」的产物。
# ══════════════════════════════════════════════════════════════════════════

# ── 前端 ─────────────────────────────────────────────────────────────────
FROM node:20-alpine AS web_image

WORKDIR /build

# 先只拷清单，锁文件不变就复用这层
COPY ./package.json ./package-lock.json /build/
RUN npm ci --no-audit --no-fund

COPY . /build
RUN npm run build \
    && test -f /build/dist/index.html \
    && echo "--- dist/index.html 引用 ---" \
    && grep -o 'assets/index-[A-Za-z0-9_-]*\.\(js\|css\)' /build/dist/index.html


# ── 后端 ─────────────────────────────────────────────────────────────────
# sqlite 驱动是 mattn/go-sqlite3，必须 CGO。
# 交叉编译要目标平台的原生 gcc，所以这里不能钉 --platform=$BUILDPLATFORM，
# 交给 buildx + QEMU 逐平台构建（arm64 那趟会慢，但架构不会串）。
#
# 为什么是 bookworm（glibc）而不是 alpine（musl）：
#   go-sqlite3 在 linux 上强制 -DHAVE_PWRITE64=1，sqlite3-binding.c 里的
#     #define osPwrite64 ((ssize_t(*)(int,const void*,size_t,off64_t))aSyscall[13].pCurrent)
#   直接用 off64_t。glibc 默认给这个类型，musl 要 _LARGEFILE64_SOURCE 才有 ——
#   在 alpine 上就是一行 `error: expected ')' before 'aSyscall'` 加一堆
#   `note: in expansion of macro 'osPwrite64'`，CI 里已经踩过一次。
#   同一份代码在 ubuntu runner 上用 glibc 编译是通过的，所以直接跟 glibc 走，
#   顺便把 CFLAGS 也补上，双保险。
FROM golang:1.21-bookworm AS server_image

ARG TARGETARCH

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

COPY ./service /build

# 用 export 而不是 go env -w：go env -w 要写 $HOME/.config/go/env，
# 容器里 HOME 或权限一变就整条 RUN 挂掉，报错还只剩一行 buildx 摘要，看不出原因。
# 代理给两个源：proxy.golang.org 在 GitHub runner 上通，goproxy.cn 在国内/亚太 runner 上通，
# 任意一个先命中就够，剩下的 direct 兜底。
RUN set -eu; \
    echo "== go 版本 =="; go version; \
    export GOPROXY="https://proxy.golang.org,https://goproxy.cn,direct"; \
    export GOSUMDB="sum.golang.org"; \
    export GOTOOLCHAIN="local"; \
    export GOFLAGS="-mod=mod"; \
    echo "== 拉依赖（单独一步，网络问题会在这里就暴露）=="; \
    go mod download; \
    echo "== 编译（CGO_ENABLED=1，mattn/go-sqlite3 要 cgo）=="; \
    CGO_ENABLED=1 \
    CGO_CFLAGS="-D_LARGEFILE64_SOURCE -D_GNU_SOURCE -O2 -g" \
    go build -trimpath \
      -ldflags="-s -w -X awadaoh/global.RUNCODE=release -X awadaoh/global.ISDOCKER=docker" \
      -o /build/awadaoh .; \
    ls -la /build/awadaoh; \
    echo "编译目标 TARGETARCH=${TARGETARCH:-未知}"; \
    od -An -tx1 -j18 -N2 /build/awadaoh


# ── 运行 ─────────────────────────────────────────────────────────────────
# 运行层也必须是 glibc：CGO 编出来的二进制动态链接 libc，
# 放进 alpine 会直接 "not found"（缺 ld-linux-aarch64.so.1）。
FROM debian:bookworm-slim

# TARGETARCH 是 buildx 自动注入的 build arg，但**每个 stage 都要自己 ARG 一次**，
# 上一个 stage 声明过的不会传下来。少了这一行，下面的架构守卫永远读到空值，
# 一上来就 `!! TARGETARCH 未注入`（CI 里已经踩过）。
ARG TARGETARCH

LABEL org.opencontainers.image.title="Awadaoh" \
      org.opencontainers.image.description="自托管导航面板 / NAS 首页（前后端源码构建）" \
      org.opencontainers.image.source="https://github.com/awahello/awadaoh"

WORKDIR /app

COPY --from=web_image /build/dist /app/web
COPY --from=server_image /build/awadaoh /app/awadaoh
COPY ./service/assets/conf.example.ini /app/conf.example.ini
COPY ./docker/pro-entrypoint.sh /app/docker-entrypoint.sh

ENV TZ=Asia/Shanghai

EXPOSE 3055

# 架构守卫：buildx 不会校验 COPY 进来的文件架构，这里自己读 ELF e_machine。
# 0x3e=amd64(3e00) 0xb7=arm64(b700)。不对就当场炸，别等用户 exec format error。
RUN set -eu; \
    case "${TARGETARCH:-}" in \
      amd64) want=3e00 ;; \
      arm64) want=b700 ;; \
      "") echo "!! TARGETARCH 未注入"; exit 1 ;; \
      *) echo "!! 不支持的 TARGETARCH=${TARGETARCH}"; exit 1 ;; \
    esac; \
    got="$(od -An -tx1 -j18 -N2 /app/awadaoh | tr -d ' \n')"; \
    echo "架构守卫: TARGETARCH=${TARGETARCH} ELF e_machine=${got} 期望=${want}"; \
    if [ "$got" != "$want" ]; then \
      echo "!! /app/awadaoh 架构不符，这个镜像打出来必然 exec format error"; exit 1; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends bash ca-certificates tzdata curl; \
    rm -rf /var/lib/apt/lists/*; \
    chmod +x /app/awadaoh /app/docker-entrypoint.sh; \
    ls -la /app/web/index.html

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:3055/ || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
