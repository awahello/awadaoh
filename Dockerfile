# syntax=docker/dockerfile:1

# ── 前端构建 ─────────────────────────────────────────────────────
FROM node:20-alpine AS web_image

RUN npm install -g pnpm@8

WORKDIR /build

COPY ./package.json /build
COPY ./pnpm-lock.yaml /build

RUN pnpm install --frozen-lockfile

COPY . /build

RUN pnpm run build


# ── 后端构建 ─────────────────────────────────────────────────────
# 注意：sqlite3 依赖 cgo，交叉编译需要目标平台原生 gcc，
# 因此不使用 BUILDPLATFORM，交给 buildx + QEMU 逐平台构建。
FROM golang:1.21-alpine3.18 AS server_image

WORKDIR /build

COPY ./service .

RUN apk add --no-cache bash curl gcc git musl-dev

RUN go env -w GO111MODULE=on \
    && export PATH=$PATH:/go/bin \
    && go install -a -v github.com/go-bindata/go-bindata/...@latest \
    && go install -a -v github.com/elazarl/go-bindata-assetfs/...@latest \
    && go-bindata-assetfs -o=assets/bindata.go -pkg=assets assets/... \
    && CGO_ENABLED=1 go build -o awadaoh \
        --ldflags="-X awadaoh/global.RUNCODE=release -X awadaoh/global.ISDOCKER=docker" .


# ── 运行镜像 ─────────────────────────────────────────────────────
FROM alpine:3.19

LABEL org.opencontainers.image.title="Awadaoh" \
      org.opencontainers.image.description="自托管导航面板 / NAS 首页" \
      org.opencontainers.image.source="https://github.com/awahello/awadaoh"

WORKDIR /app

COPY --from=web_image /build/dist /app/web
COPY --from=server_image /build/awadaoh /app/awadaoh

ENV TZ=Asia/Shanghai

EXPOSE 3055

RUN apk add --no-cache bash ca-certificates su-exec tzdata curl \
    && chmod +x ./awadaoh \
    && ./awadaoh -config

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:3055/ || exit 1

CMD ["./awadaoh"]
