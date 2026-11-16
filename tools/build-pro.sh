#!/usr/bin/env bash
# AKKdaoh · 组装 PRO 镜像物料
#
# 输入：官方 release 解压目录（含 sun-panel 二进制 + web/）
# 输出：<OUT>/akkdaoh        已解锁 PRO 的后端二进制
#       <OUT>/web/           已注入导航站主题、已解锁 isPro 的前端包
#
# 用法：
#   ./tools/build-pro.sh /path/to/sun-panel_vX_linux_arm64
#   ./tools/build-pro.sh /path/to/sun-panel_vX_linux_arm64 pro/arm64
#   ARCH=amd64 ./tools/build-pro.sh ... pro/amd64
#
# CI 用法见 .github/workflows/docker-pro.yml
set -euo pipefail

SRC="${1:-}"
OUT="${2:-}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"

if [ -z "$SRC" ] || [ ! -d "$SRC" ]; then
  echo "用法: $0 <解压后的 release 目录> [输出目录]"; exit 1
fi
[ -f "$SRC/sun-panel" ] || { echo "缺少 $SRC/sun-panel"; exit 1; }
[ -d "$SRC/web" ] || { echo "缺少 $SRC/web"; exit 1; }

[ -n "$OUT" ] || OUT="$ROOT/pro"

echo "==> 输出目录: $OUT"
rm -rf "$OUT"
mkdir -p "$OUT"

echo "==> 复制二进制与前端"
cp "$SRC/sun-panel" "$OUT/akkdaoh"
chmod +x "$OUT/akkdaoh"
cp -r "$SRC/web" "$OUT/web"

echo "==> 后端补丁: ProIsExpired -> 恒 false"
"$PY" "$ROOT/tools/patch-pro.py" "$OUT/akkdaoh"

echo "==> 前端补丁: isPro -> !0（兜底，后端已返回 true 时无命中）"
"$PY" "$ROOT/tools/patch-web.py" "$OUT/web" || true

echo "==> 前端主题注入: 导航站视觉 + 自有 logo"
"$PY" "$ROOT/tools/web-inject.py" "$OUT/web"

echo "==> 清理备份文件"
rm -f "$OUT/akkdaoh.orig"
find "$OUT/web" -name "*.bak" -delete 2>/dev/null || true

echo "==> 复核"
"$PY" "$ROOT/tools/patch-pro.py" "$OUT/akkdaoh" --check
"$PY" "$ROOT/tools/web-inject.py" "$OUT/web" --check

SIZE=$(du -h "$OUT/akkdaoh" | cut -f1)
cat <<EOF

完成。
  后端 $OUT/akkdaoh  ($SIZE)
  前端 $OUT/web

构建镜像：
  docker buildx build --platform linux/amd64,linux/arm64 \\
    -f Dockerfile.pro -t awahello/akkdaoh:latest .
EOF
