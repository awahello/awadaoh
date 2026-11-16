#!/usr/bin/env bash
# AKKdaoh · 组装 PRO 镜像物料
#
# 输入：官方 PRO 版 release 包（sun-panel 二进制 + web/ 目录）
# 输出：./pro/akkdaoh  打补丁后的二进制
#       ./pro/web/     已解锁 isPro 的前端包
#       ./pro/conf.ini 生成的首份配置
#
# 用法：
#   ./tools/build-pro.sh /path/to/sun-panel_vX_linux_arm64
#   docker build -f Dockerfile.pro -t awahello/akkdaoh-pro:latest .
set -euo pipefail

SRC="${1:-}"
if [ -z "$SRC" ] || [ ! -d "$SRC" ]; then
  echo "用法: $0 <解压后的 release 目录>"; exit 1
fi
[ -f "$SRC/sun-panel" ] || { echo "缺少 $SRC/sun-panel"; exit 1; }
[ -d "$SRC/web" ] || { echo "缺少 $SRC/web"; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/pro"
PY="${PYTHON:-python3}"

rm -rf "$OUT"
mkdir -p "$OUT"

echo "==> 复制二进制与前端"
cp "$SRC/sun-panel" "$OUT/akkdaoh"
chmod +x "$OUT/akkdaoh"
cp -r "$SRC/web" "$OUT/web"

echo "==> 后端补丁：ProIsExpired -> 恒 false"
"$PY" "$ROOT/tools/patch-pro.py" "$OUT/akkdaoh"

echo "==> 前端补丁：isPro -> true"
"$PY" "$ROOT/tools/patch-web.py" "$OUT/web"

echo "==> 剥离备份文件"
rm -f "$OUT/akkdaoh.orig"

echo "==> 校验"
"$PY" "$ROOT/tools/patch-pro.py" "$OUT/akkdaoh" --check
"$PY" "$ROOT/tools/patch-web.py" "$OUT/web" --check || true

echo
echo "完成。构建镜像："
echo "  docker build -f Dockerfile.pro -t awahello/akkdaoh-pro:latest ."
