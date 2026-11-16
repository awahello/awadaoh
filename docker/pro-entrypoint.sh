#!/bin/sh
# ── Awadaoh PRO 容器入口 ────────────────────────────────────────
# 只干一件事：把监听端口钉死在 3055，然后 exec 后端。
#
# 为什么需要它：
#   上游二进制内嵌的默认端口是 3002。compose 把宿主机 ./conf 挂到 /app/conf 之后，
#   容器里那份 http_port=3055 的 conf.ini 就被盖掉了；宿主机目录一开始是空的，
#   二进制会自己生成一份 http_port=3002 的 conf.ini，于是日志里永远是
#   `HTTP: 0.0.0.0:3002`，而 compose 映射的是 3055:3055，对不上。
#   每次启动在这里改回来，用户就不用管宿主机 conf/ 里到底写了什么。
set -eu

CONF=/app/conf/conf.ini
PORT="${AWADAOH_HTTP_PORT:-3055}"

mkdir -p /app/conf /app/database /app/uploads /app/runtime

if [ ! -f "$CONF" ]; then
  if [ -f /app/conf.example.ini ]; then
    cp -f /app/conf.example.ini "$CONF"
  else
    printf '[base]\nhttp_port=%s\n' "$PORT" > "$CONF"
  fi
fi

sed -i "s|^[[:space:]]*http_port.*|http_port=${PORT}|" "$CONF"
grep -q "^http_port=${PORT}$" "$CONF" || echo "http_port=${PORT}" >> "$CONF"

echo "[awadaoh] 启动：http_port=${PORT}  conf=${CONF}"

exec /app/awadaoh "$@"
