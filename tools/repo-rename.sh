#!/usr/bin/env bash
# Awadaoh · 一条命令改 GitHub 项目页
#
# 做四件事（全部走 REST API，api.github.com 可直连）：
#   1) 仓库改名   akkdaoh -> awadaoh
#   2) 项目页简介  description
#   3) 主页链接    homepage
#   4) Topics 标签
#   5) 顺手把本地 git remote 指向新地址
#
# 用法：
#   GH_TOKEN=github_pat_xxx ./tools/repo-rename.sh
#   GH_TOKEN=ghp_xxx OWNER=awahello NEW=awadaoh ./tools/repo-rename.sh
#
# Token 权限：
#   fine-grained PAT -> 选中 awahello/akkdaoh -> Repository permissions -> Administration: Read and write
#   classic PAT      -> 勾 repo（旧版会顺带 administration 权限）
#
# 只改名不要元信息：SKIP_META=1 GH_TOKEN=... ./tools/repo-rename.sh
set -euo pipefail

OWNER="${OWNER:-awahello}"
OLD="${OLD:-akkdaoh}"
NEW="${NEW:-awadaoh}"
API="${API:-https://api.github.com}"
DESC="${DESC:-自托管导航面板 / NAS 首页 / 浏览器起始页}"
HOMEURL="${HOMEURL:-https://www.akkdiy.cn}"
TOPICS_JSON="${TOPICS_JSON:-[\"navigation\",\"homepage\",\"startpage\",\"nas\",\"self-hosted\",\"docker\",\"bookmarks\",\"python\"]}"

: "${GH_TOKEN:?需要 GH_TOKEN（PAT，带 Administration 写权限）}"

api() {
  local method="$1" path="$2" data="${3:-}"
  local args=(-sS -X "$method" "${API}${path}"
    -H "Authorization: Bearer ${GH_TOKEN}"
    -H "Accept: application/vnd.github+json"
    -H "X-GitHub-Api-Version: 2022-11-28"
    -H "User-Agent: awadaoh-rename")
  [ -n "$data" ] && args+=(-H "Content-Type: application/json" -d "$data")
  curl "${args[@]}" -w '\n__HTTP__%{http_code}\n'
}

check() {
  local raw="$1" label="$2"
  local body="${raw%$'\n'__HTTP__*}"
  local code="${raw##*__HTTP__}"
  code="${code//[$'\r\n']/}"
  if [ "$code" = "200" ] || [ "$code" = "201" ]; then
    echo "==> ${label}  OK (${code})"
    return 0
  fi
  echo "==> ${label}  失败 (HTTP ${code})"
  echo "$body" | sed -e 's/^/    /'
  return 1
}

echo "==> 目标：${OWNER}/${OLD} -> ${OWNER}/${NEW}"

# 0) 先确认 token 是谁、有没有权限
WHO="$(api GET /user)"
if ! check "$WHO" "校验 token"; then
  echo "    token 无效或已过期，先去 https://github.com/settings/tokens 重新生成"
  exit 1
fi
LOGIN="$(printf '%s' "$WHO" | sed -n 's/.*"login"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
echo "    当前身份：${LOGIN:-unknown}"

# 1) 改名（同时可以带上元信息）
if [ "${SKIP_META:-0}" = "1" ]; then
  RENAME_BODY="{\"name\":\"${NEW}\"}"
else
  RENAME_BODY="{\"name\":\"${NEW}\",\"description\":\"${DESC}\",\"homepage\":\"${HOMEURL}\"}"
fi
RES="$(api PATCH "/repos/${OWNER}/${OLD}" "$RENAME_BODY")"
if ! check "$RES" "改名 + 简介 + 主页"; then
  echo "    如果是 403：token 缺 Administration 写权限"
  echo "    如果是 422：新名字被占用，或与已有仓库冲突"
  exit 1
fi
echo "    新地址：https://github.com/${OWNER}/${NEW}"

# 2) Topics（改名后路径要用新名字）
if [ "${SKIP_META:-0}" != "1" ]; then
  RES="$(api PUT "/repos/${OWNER}/${NEW}/topics" "{\"names\":${TOPICS_JSON}}")"
  check "$RES" "Topics ${TOPICS_JSON}" || true
fi

# 3) 本地 remote 跟着改
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if git rev-parse --git-dir >/dev/null 2>&1; then
  git remote set-url origin "https://github.com/${OWNER}/${NEW}.git"
  echo "==> 本地 remote -> $(git remote get-url origin)"
fi

cat <<EOF

完成。
  项目页  https://github.com/${OWNER}/${NEW}
  老地址  https://github.com/${OWNER}/${OLD} 会自动 301 到新地址，
          已 clone 的机器不用改，下次 push 之前把 remote 换一下更干净。

  git push -u origin main
EOF
