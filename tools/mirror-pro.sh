#!/usr/bin/env bash
# Awadaoh · 把上游 PRO 包镜像到自己的 release
#
# 只在需要「以后不再从别人仓库下载」时跑一次。之后 CI / 本地都走
# tools/fetch-pro.sh，只认自己仓库的包名：
#   awadaoh-pro_<TAG>_linux_amd64.tar.gz
#   awadaoh-pro_<TAG>_linux_arm64.tar.gz
#
# 用法：
#   ./tools/mirror-pro.sh v2.0.2-beta261110 ./sun-panel_v2.0.2-beta261110_linux_arm64.tar.gz
#   ARCH=amd64 ./tools/mirror-pro.sh v2.0.2-beta261110 ./pkg.tar.gz
#
# 需要：gh（已登录，有 release 权限）
set -euo pipefail

TAG="${1:-}"
SRC="${2:-}"
MIRROR_REPO="${MIRROR_REPO:-${GITHUB_REPOSITORY:-awahello/awadaoh}}"

if [ -z "$TAG" ] || [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  echo "用法: $0 <tag> <本地包路径>"; exit 1
fi

command -v gh >/dev/null 2>&1 || { echo "需要 gh CLI"; exit 1; }

# 猜架构：显式 ARCH 优先，其次按文件名
ARCH="${ARCH:-}"
if [ -z "$ARCH" ]; then
  case "$SRC" in
    *arm64*|*aarch64*) ARCH=arm64 ;;
    *amd64*|*x86_64*)  ARCH=amd64 ;;
    *)                 ARCH=amd64 ;;
  esac
fi

NAME="awadaoh-pro_${TAG}_linux_${ARCH}.tar.gz"
TMP="$(mktemp -d)/${NAME}"
cp "$SRC" "$TMP"

# release 不在就建
gh release view "$TAG" --repo "$MIRROR_REPO" >/dev/null 2>&1 \
  || gh release create "$TAG" --repo "$MIRROR_REPO" --title "$TAG" --notes "PRO 物料镜像"

gh release upload "$TAG" "$TMP" --repo "$MIRROR_REPO" --clobber

echo "==> 已上传: https://github.com/${MIRROR_REPO}/releases/download/${TAG}/${NAME}"
echo "    之后 ./tools/fetch-pro.sh ${ARCH} ${TAG} 只从自己的仓库取。"
