#!/usr/bin/env bash
# Awadaoh · 取 PRO 物料包
#
# 顺序：
#   1) 先看自己仓库的 release 里有没有镜像包  awadaoh-pro_<TAG>_linux_<ARCH>.tar.gz
#   2) 没有才回退上游同版本 release
#
# 想彻底不用上游地址：把包镜像到自己的 release 一次（见 tools/mirror-pro.sh），
# 之后所有机器、CI 都只从自己的仓库下载。
#
# 用法：
#   ./tools/fetch-pro.sh arm64
#   ./tools/fetch-pro.sh amd64 v2.0.2-beta261110 rel-amd64
#
# 环境变量：
#   MIRROR_REPO    自己的仓库        默认 $GITHUB_REPOSITORY，再默认 awahello/awadaoh
#   UPSTREAM_REPO  上游仓库（回退用） 默认 hslr-s/sun-panel
#   UPSTREAM_TAG   上游 tag          默认 v2.0.2-beta261110
set -euo pipefail

ARCH="${1:-}"
TAG="${2:-${UPSTREAM_TAG:-v2.0.2-beta261110}}"
OUT="${3:-rel-${ARCH}}"

MIRROR_REPO="${MIRROR_REPO:-${GITHUB_REPOSITORY:-awahello/awadaoh}}"
UPSTREAM_REPO="${UPSTREAM_REPO:-hslr-s/sun-panel}"

if [ "$ARCH" != "amd64" ] && [ "$ARCH" != "arm64" ]; then
  echo "用法: $0 <amd64|arm64> [tag] [输出目录]"; exit 1
fi

OWN_NAME="awadaoh-pro_${TAG}_linux_${ARCH}.tar.gz"
UP_NAME="sun-panel_${TAG}_linux_${ARCH}.tar.gz"

mkdir -p "$OUT"
TARBALL="$(mktemp -d)/pkg.tar.gz"
URL_USED=""

try_get() {
  local label="$1" url="$2"
  echo "==> 尝试 ${label}: ${url}"
  if curl -fsSL --retry 3 --retry-delay 2 --retry-all-errors \
      --max-time 300 -o "$TARBALL" "$url"; then
    echo "==> 命中 ${label}"
    URL_USED="$url"
    return 0
  fi
  echo "==> 未命中（跳过）"
  return 1
}

GOT=0
# 1) 自己的镜像包
if try_get "自己的镜像包" \
    "https://github.com/${MIRROR_REPO}/releases/download/${TAG}/${OWN_NAME}"; then
  GOT=1
fi
# 2) 回退上游
if [ "$GOT" = "0" ] && try_get "上游 release" \
    "https://github.com/${UPSTREAM_REPO}/releases/download/${TAG}/${UP_NAME}"; then
  GOT=1
fi

if [ "$GOT" = "0" ]; then
  cat <<EOF

取包失败。两条路：
  A. 先镜像一次到自己的 release（之后就不用管上游了）：
       gh release upload ${TAG} <本地包> --repo ${MIRROR_REPO}
     或者用：./tools/mirror-pro.sh ${TAG} <本地包>

  B. 只用自己仓库：MIRROR_REPO=${MIRROR_REPO} ./tools/fetch-pro.sh ${ARCH} ${TAG} ${OUT}
     并确保 ${MIRROR_REPO} 的 ${TAG} release 里有 ${OWN_NAME}
EOF
  exit 1
fi

rm -rf "$OUT"; mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
# Windows/Git Bash 下 mktemp 出来的路径是 C:\... ，GNU tar 会把 "C:" 当远端主机，
# 加 --force-local 才不会报 "Cannot connect to C"。Linux 的 GNU tar 同样接受该参数。
TARX="tar"
if tar --force-local --version >/dev/null 2>&1; then TARX="tar --force-local"; fi
$TARX -xzf "$TARBALL" -C "$OUT" --strip-components=1
rm -f "$TARBALL" 2>/dev/null || true

[ -f "$OUT/awadaoh" ] || [ -f "$OUT/sun-panel" ] || { echo "包内缺少后端二进制"; exit 1; }
[ -d "$OUT/web" ]      || { echo "包内缺少 web/ 目录"; exit 1; }

# 包里的可执行文件可能叫 sun-panel，统一成 awadaoh，后面对齐
if [ ! -f "$OUT/awadaoh" ] && [ -f "$OUT/sun-panel" ]; then
  mv "$OUT/sun-panel" "$OUT/awadaoh"
fi
chmod +x "$OUT/awadaoh"

# 包名写着 arm64 不代表里面的二进制是 arm64。
# 这里当场核一次 ELF 头，把「来源包装错架构」挡在构建之外，
# 而不是等镜像推上去、用户 docker compose up 才 exec format error。
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
echo "==> 校验包内二进制架构（期望 ${ARCH}）"
if ! "$PY" "$ROOT/tools/elfarch.py" "$OUT/awadaoh" --expect "$ARCH"; then
  echo
  echo "来源包 $ARCH 里装的不是 $ARCH 二进制。"
  echo "  包地址: ${URL_USED}"
  echo "换一条路："
  echo "  1) 把正确架构的包镜像到自己的 release：./tools/mirror-pro.sh ${TAG} <本地包>"
  echo "  2) 或显式指定上游 tag：./tools/fetch-pro.sh ${ARCH} <别的 tag> ${OUT}"
  exit 1
fi

echo "==> 就绪: $OUT/awadaoh   $OUT/web"
