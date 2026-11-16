#!/usr/bin/env bash
# Awadaoh · 组装 PRO 镜像物料
#
# 输入：release 解压目录（含 sun-panel 或 awadaoh 二进制 + web/）
# 输出：<OUT>/awadaoh        已解锁 PRO 的后端二进制
#       <OUT>/web/           我们自己 src/ 的编译产物（dist）+ 上游 custom/static 挂载点 + 注入的主题
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
BIN="$SRC/sun-panel"
[ -f "$BIN" ] || BIN="$SRC/awadaoh"
[ -f "$BIN" ] || { echo "缺少 $SRC/sun-panel（或 awadaoh）"; exit 1; }
[ -d "$SRC/web" ] || { echo "缺少 $SRC/web"; exit 1; }

[ -n "$OUT" ] || OUT="$ROOT/pro"

echo "==> 输出目录: $OUT"
rm -rf "$OUT"
mkdir -p "$OUT"

# 期望架构：显式 ARCH 优先，否则从输出目录名猜（pro/arm64 -> arm64）。
# 猜不到就不校验，只打印。
EXPECT="${ARCH:-$(basename "$OUT")}"
case "$EXPECT" in
  amd64|arm64) ;;
  *) EXPECT="" ;;
esac

echo "==> 复制二进制"
cp "$BIN" "$OUT/awadaoh"
chmod +x "$OUT/awadaoh"

# 前端必须用我们自己的 dist（由 src/ 编译而来）。
# 以前这里 cp 的是 $SRC/web，也就是上游预编译前端包，所以镜像里跑的从来不是我们的界面：
# 打开域名第一眼是登录框，左侧分类栏 / 搜索框 / 前台无登录统统不在。
# 上游 web 里只有 custom/ static/ micro-apps/ 这几个运行时挂载点需要保留。
if [ ! -f "$ROOT/dist/index.html" ]; then
  echo
  echo "构建中止：$ROOT/dist/index.html 不存在。"
  echo "前端要用我们自己的源码产物，先跑："
  echo "  npm ci && npm run build"
  exit 1
fi

echo "==> 前端: 使用 $ROOT/dist（自有源码产物）"
rm -rf "$OUT/web"
cp -r "$ROOT/dist" "$OUT/web"
for d in custom static micro-apps; do
  if [ -d "$SRC/web/$d" ] && [ ! -d "$OUT/web/$d" ]; then
    cp -r "$SRC/web/$d" "$OUT/web/$d"
    echo "    补入上游挂载点: $d/"
  fi
done

# 这一行是整个脚本里最重要的一行。
# buildx 打 linux/arm64 标签时不会检查 COPY 进去的文件是不是 arm64；
# 上游 arm64 包若装错、或 pro/arm64 被上一次 amd64 构建污染，
# 以前会一路绿灯推出镜像，等用户 docker compose up 才 exec format error。
echo "==> 校验二进制真实架构（期望 ${EXPECT:-未知}）"
if ! "$PY" "$ROOT/tools/elfarch.py" "$OUT/awadaoh" ${EXPECT:+--expect "$EXPECT"}; then
  echo
  echo "构建中止：$OUT/awadaoh 的 ELF 架构与目标不符。"
  echo "来源包: $SRC"
  echo "先确认来源包对不对："
  echo "  python3 tools/elfarch.py $BIN"
  exit 1
fi
echo "==> 二进制 sha256: $(sha256sum "$OUT/awadaoh" | cut -d' ' -f1)"

echo "==> 后端补丁: ProIsExpired -> 恒 false"
"$PY" "$ROOT/tools/patch-pro.py" "$OUT/awadaoh"

echo "==> 前端补丁: isPro -> !0（兜底，后端已返回 true 时无命中）"
"$PY" "$ROOT/tools/patch-web.py" "$OUT/web" || true

echo "==> 前端主题注入: 导航站视觉 + 自有 logo"
# --no-catnav：前端现在是自己的 dist，左侧分类栏已经编在 src/ 里了。
# 再往 /custom/index.js 塞一份 DOM 补丁会出现两条分类栏。
"$PY" "$ROOT/tools/web-inject.py" "$OUT/web" --no-catnav

# 品牌收尾。放在最后：主题注入写进去的 css/js 也一起过一遍，
# 免得前面换完、后面又被注回 Sun-Panel。
# 后端二进制只能做等长替换（Go 字符串长度烘在指令里），规则见 rebrand.py 头部注释。
echo "==> 抹掉上游品牌: Sun-Panel -> Awadaoh"
"$PY" "$ROOT/tools/rebrand.py" --bin "$OUT/awadaoh" --web "$OUT/web"

# 上游 release 包里带了一堆 macOS 的 AppleDouble 垃圾（._*）和 .DS_Store，
# 打进镜像纯属浪费层体积
find "$OUT/web" -name "._*" -delete 2>/dev/null || true
find "$OUT/web" -name ".DS_Store" -delete 2>/dev/null || true

echo "==> 生成 conf/conf.ini（端口 3055）"
mkdir -p "$OUT/conf"
if [ -f "$ROOT/service/assets/conf.example.ini" ]; then
  sed -e 's/^[[:space:]]*http_port.*/http_port=3055/' \
      "$ROOT/service/assets/conf.example.ini" > "$OUT/conf/conf.ini"
else
  printf '[base]\nhttp_port=3055\n' > "$OUT/conf/conf.ini"
fi
grep -q '^http_port=3055' "$OUT/conf/conf.ini" || { echo "conf.ini 端口写入失败"; exit 1; }

echo "==> 清理备份文件"
rm -f "$OUT/awadaoh.orig"
find "$OUT/web" -name "*.bak" -delete 2>/dev/null || true

# 前端与架构无关，Dockerfile.pro 读的是 pro/web，所以按架构产出后再同步一份公共的，
# 否则 docker build 会在 COPY ./pro/web 这一步挂掉（CI 里表现为 du: pro/web: No such file）。
if [ "$(cd "$OUT" && pwd)" != "$ROOT/pro/web" ]; then
  mkdir -p "$ROOT/pro"
  rm -rf "$ROOT/pro/web"
  cp -r "$OUT/web" "$ROOT/pro/web"
  echo "==> 公共前端: $ROOT/pro/web"
fi

echo "==> 复核"
"$PY" "$ROOT/tools/patch-pro.py" "$OUT/awadaoh" --check
"$PY" "$ROOT/tools/web-inject.py" "$OUT/web" --no-catnav --check
"$PY" "$ROOT/tools/rebrand.py" --bin "$OUT/awadaoh" --web "$OUT/web" --check
# 打完补丁再核一次：补丁脚本若改错文件会当场炸掉
"$PY" "$ROOT/tools/elfarch.py" "$OUT/awadaoh" ${EXPECT:+--expect "$EXPECT"}

SIZE=$(du -h "$OUT/awadaoh" | cut -f1)
cat <<EOF

完成。
  后端 $OUT/awadaoh  ($SIZE, ${EXPECT:-arch?})
  前端 $OUT/web

构建镜像：
  docker buildx build --platform linux/amd64,linux/arm64 \\
    -f Dockerfile.pro -t awahello/awadaoh:latest .
EOF
