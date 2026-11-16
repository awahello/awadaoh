#!/usr/bin/env bash
# Awadaoh · 改名收尾（akkdaoh -> awadaoh）
#
# 前提：已经在 GitHub 网页上把仓库名改成 awadaoh
#       （Settings -> General -> Repository name -> Rename）
# 然后在本仓库根目录跑：
#       ./tools/rename-to-awadaoh.sh
#
# 做两件事：
#   1) git remote 指向 https://github.com/<owner>/awadaoh.git
#   2) 检查全仓库还有没有 akkdaoh / AKK 字样残留
#
# 磁盘目录改名（可选，必须在仓库外面执行，否则会把当前 shell 的 cwd 抽掉）：
#   cd .. && mv akkdaoh awadaoh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NEW_NAME="${1:-awadaoh}"
OWNER="${OWNER:-awahello}"
NEW_URL="https://github.com/${OWNER}/${NEW_NAME}.git"

echo "==> 当前 remote"
git remote -v | sed 's/^/    /'

git remote set-url origin "$NEW_URL"
echo "==> 已改为 $NEW_URL"
git remote -v | sed 's/^/    /'

echo "==> 改名残留扫描（排除 pro/ 与 .git）"
HITS="$(grep -rIn --exclude-dir=.git --exclude-dir=pro --exclude-dir=node_modules \
        -e 'akkdaoh' -e 'AKKdaoh' -e 'AKK 导航' . 2>/dev/null || true)"
if [ -n "$HITS" ]; then
  echo "$HITS" | sed 's/^/    /'
  echo "==> 上面这些还带旧名，按需替换"
else
  echo "    干净，没有旧名残留"
fi

cat <<EOF

下一步：
  git push -u origin main

如果 GitHub 那边还没改名，先改名字，否则这条 push 会 404。
EOF
