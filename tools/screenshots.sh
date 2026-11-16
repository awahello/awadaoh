#!/usr/bin/env bash
# Awadaoh · 一键重出 README / 项目页截图
#
# 干什么：
#   1) 用 tools/make-demo-config.py 生成一套演示数据（13 分类 / 73 站点 / 3 个内网站点）
#   2) 在 .shots/data 起一个临时服务（端口 3099，不碰你自己的 nav/data）
#   3) 用 headless Chrome 截前台 1 张 + 首屏 1 张 + 后台 4 张
#   4) 覆盖 nav/doc/*.png 与 doc/preview.png，然后关服务、删临时页
#
# 用法：
#   ./tools/screenshots.sh              # 全部重出
#   ./tools/screenshots.sh home preview # 只重出指定几张
#   PORT=3099 CHROME=/path/to/chrome ./tools/screenshots.sh
#
# 依赖：python3、curl、Google Chrome（或 Chromium）
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${PORT:-3099}"
PY="${PYTHON:-python}"
SHOTDIR="$ROOT/.shots"
DATA="$SHOTDIR/data"
URL="http://127.0.0.1:$PORT"

# ── Chrome 位置 ───────────────────────────────────────────────
if [ -z "${CHROME:-}" ]; then
  for c in \
    "/c/Program Files/Google/Chrome/Application/chrome.exe" \
    "/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" \
    "$LOCALAPPDATA/Google/Chrome/Application/chrome.exe" \
    "/usr/bin/google-chrome" "/usr/bin/chromium" "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
    [ -x "$c" ] && CHROME="$c" && break
  done
fi
[ -n "${CHROME:-}" ] && [ -x "${CHROME:-}" ] || { echo "找不到 Chrome，用 CHROME=/path/to/chrome 指定"; exit 1; }

want="${*:-home preview admin-groups admin-sites admin-sync admin-private}"
has() { case " $want " in *" $1 "*) return 0;; *) return 1;; esac; }

mkdir -p "$SHOTDIR"

# ── 演示数据 ──────────────────────────────────────────────────
echo "==> 生成演示配置"
"$PY" tools/make-demo-config.py || exit 1

# ── 截图专用的 token 注入页（同源，跑完就删）────────────────────
SHOTPAGE="$ROOT/nav/static/_shot.html"
cat > "$SHOTPAGE" <<'HTML'
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>shot</title>
<style>html,body{margin:0;height:100%;background:#0b1220}iframe{border:0;width:100vw;height:100vh;display:block}</style>
</head><body>
<script>
	/* 截图专用：同源注入 token 再挂 /admin，截完即删，不参与部署 */
	var q = new URLSearchParams(location.search), tok = q.get('tok') || '',
		tab = q.get('tab') || '', card = q.get('card') || '';
	try { sessionStorage.setItem('ak-nav-token', tok); localStorage.setItem('ak-nav-token', tok); } catch (e) {}
	var f = document.createElement('iframe');
	f.src = '/admin';
	f.onload = function () {
		var d = null;
		try { d = f.contentDocument; } catch (e) { return; }
		var n = 0, timer = setInterval(function () {
			if (++n > 40 || !d || !d.body) { if (n > 40) clearInterval(timer); return; }
			var btn = tab ? d.querySelector('.tab[data-tab="' + tab + '"]') : null;
			if (btn) btn.click();
			if (card) {
				var cards = d.querySelectorAll('.card');
				for (var i = 0; i < cards.length; i++) {
					if ((cards[i].textContent || '').indexOf(card) >= 0) { cards[i].scrollIntoView({ block: 'center' }); break; }
				}
			}
			clearInterval(timer);
		}, 200);
	};
	document.body.appendChild(f);
</script>
</body></html>
HTML

cleanup() {
  [ -n "${SRV_PID:-}" ] && kill "$SRV_PID" 2>/dev/null
  rm -f "$SHOTPAGE"
  rm -rf "$SHOTDIR/c1" "$SHOTDIR/c2"
}
trap cleanup EXIT

# ── 起服务 ────────────────────────────────────────────────────
echo "==> 起演示服务 $URL"
( cd nav && DATA_DIR="$DATA" PORT="$PORT" exec "$PY" server.py ) >"$SHOTDIR/server.log" 2>&1 &
SRV_PID=$!
for i in $(seq 1 40); do
  curl -sf -o /dev/null "$URL/api/config" && break
  sleep 0.3
done
curl -sf -o /dev/null "$URL/api/config" || { echo "服务没起来，看 $SHOTDIR/server.log"; exit 1; }

TOK=$(curl -sS -X POST "$URL/api/login" -H 'Content-Type: application/json' \
      --data '{"password":"demo"}' | "$PY" -c 'import sys,json;print(json.load(sys.stdin).get("token",""))')
[ -n "$TOK" ] || { echo "登录失败，拿不到 token"; exit 1; }

enc() { "$PY" -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1"; }

shot() { # shot 文件名 宽x高 URL [等待预算ms]
  local out="$1" size="$2" url="$3" budget="${4:-6000}" profile="$SHOTDIR/c1"
  case "$out" in admin-*) profile="$SHOTDIR/c2";; esac
  echo "      -> $out  ($size)"
  timeout 120 "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
    --force-device-scale-factor=1 --window-size="$size" \
    --virtual-time-budget="$budget" --timeout=16000 \
    --user-data-dir="$profile" --screenshot="$SHOTDIR/$out" "$url" >/dev/null 2>&1
  [ -s "$SHOTDIR/$out" ] || { echo "   !! $out 没截出来"; return 1; }
}

echo "==> 截图"
has home          && shot home.png          1440,900  "$URL/"                       && cp "$SHOTDIR/home.png"          nav/doc/home.png
has preview       && shot preview.png       1440,960  "$URL/"                       && cp "$SHOTDIR/preview.png"       doc/preview.png
has admin-groups  && shot admin-groups.png  1440,1000 "$URL/_shot.html?tok=$TOK&tab=groups" && cp "$SHOTDIR/admin-groups.png"  nav/doc/admin-groups.png
has admin-sites   && shot admin-sites.png   1440,1000 "$URL/_shot.html?tok=$TOK&tab=sites&card=$(enc '工具')" && cp "$SHOTDIR/admin-sites.png"   nav/doc/admin-sites.png
has admin-sync    && shot admin-sync.png    1440,1000 "$URL/_shot.html?tok=$TOK&tab=sync&card=$(enc '当前状态')" && cp "$SHOTDIR/admin-sync.png"    nav/doc/admin-sync.png
has admin-private && shot admin-private.png 1440,1000 "$URL/_shot.html?tok=$TOK&tab=settings&card=$(enc '内网地址保护')" && cp "$SHOTDIR/admin-private.png" nav/doc/admin-private.png

echo
echo "==> 结果"
ls -l nav/doc/*.png doc/preview.png 2>/dev/null | awk '{printf "    %8d  %s\n", $5, $9}'
echo
echo "提交： git add nav/doc doc/preview.png && git commit -m 'docs: 重出截图'"
