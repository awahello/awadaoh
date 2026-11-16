#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Awadaoh Nav · 极简自托管导航站

一个文件的后端，只用标准库：
  - 前台 /        打开就是导航，不需要登录
  - 后台 /admin   改分组、改站点、导入 Chrome 书签
  - 数据 config.json，随手备份

运行：
    python3 server.py                 # 默认 0.0.0.0:3055
    PORT=3000 python3 server.py
    DATA_DIR=/data python3 server.py

环境变量：
    PORT       监听端口，默认 3055
    HOST       监听地址，默认 0.0.0.0
    DATA_DIR   数据目录，默认 ./data
    ADMIN_PASS 后台密码，默认 admin123（首次启动写入 config）
    BOOKMARK_FILE  Chrome 的 Bookmarks 文件路径，给了就默认开启自动同步

书签自动同步原理：
    Chrome 登录 Google 账号后的书签，最终都落在本地 profile 的
    "Bookmarks" JSON 文件里（Google 同步只是把这个文件改掉）。
    所以监听这个文件的 mtime/hash，一变就重新解析并入 config，就等价于
    "和 Google 书签自动同步"，不需要任何 Google API / OAuth。

内网地址保护：
    导入/保存时按 host 判内网（私有 IP 段、*.lan/*.local、单标签主机名、file://），
    打上 private 标记。/api/config 对未登录访客把 private 站点的 url 置空
    （privateMode=mask）或整条不下发（hide）；带有效 token 才给真实地址。
    这样挂到公网也不会把内网拓扑贴出去。
"""

import base64
import hashlib
import ipaddress
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(BASE, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEFAULT_PASS = os.environ.get("ADMIN_PASS") or "admin123"
MAX_BODY = 32 * 1024 * 1024  # 32MB，书签 HTML 一般 < 2MB

# 运行时 token（重启失效，够用）
TOKENS = {}
TOKEN_TTL = 12 * 3600


# ─────────────────────────── 数据层 ───────────────────────────

def new_id(prefix="i"):
    return prefix + secrets.token_hex(4)


def default_config():
    return {
        "title": "Awadaoh 导航",
        "subtitle": "自托管起始页",
        "footer": "www.akkdiy.cn",
        "footerUrl": "https://www.akkdiy.cn",
        "searchEngine": "https://www.bing.com/search?q=%s",
        "engine": "bing",
        "engines": [
            {"id": "bing", "name": "Bing", "url": "https://www.bing.com/search?q=%s"},
            {"id": "google", "name": "Google", "url": "https://www.google.com/search?q=%s"},
            {"id": "baidu", "name": "百度", "url": "https://www.baidu.com/s?wd=%s"},
            {"id": "ddg", "name": "DuckDuckGo", "url": "https://duckduckgo.com/?q=%s"},
            {"id": "github", "name": "GitHub", "url": "https://github.com/search?q=%s"},
            {"id": "bili", "name": "哔哩哔哩", "url": "https://search.bilibili.com/all?keyword=%s"},
        ],
        "password": DEFAULT_PASS,
        "theme": "dark",
        # 内网地址处理：mask=前台打码 / hide=前台完全不下发 / show=原样显示
        "privateMode": "mask",
        # 域名解析复查（公司内网域名 → 10.x 这种），默认关，开了导入会慢
        "privateDns": False,
        # 书签自动同步（监听 Chrome/Edge 的 Bookmarks JSON 文件）
        "sync": {
            "enabled": os.environ.get("BOOKMARK_FILE") not in (None, ""),
            "path": os.environ.get("BOOKMARK_FILE") or "",
            "interval": 300,          # 秒，最短 30
            "mode": "merge",          # merge=并入 / replace=整站替换
            "lastSync": 0,
            "lastResult": "",
        },
        "groups": [
            {
                "id": new_id("g"),
                "name": "常用",
                "icon": "⭐",
                "hidden": False,
                "sites": [
                    {"id": new_id("s"), "title": "GitHub", "url": "https://github.com",
                     "desc": "代码托管", "icon": ""},
                    {"id": new_id("s"), "title": "Bing", "url": "https://www.bing.com",
                     "desc": "搜索", "icon": ""},
                    {"id": new_id("s"), "title": "AKK DIY", "url": "https://www.akkdiy.cn",
                     "desc": "我的站点", "icon": ""},
                ],
            },
            {
                "id": new_id("g"),
                "name": "工具",
                "icon": "🧰",
                "hidden": False,
                "sites": [
                    {"id": new_id("s"), "title": "Docker Hub", "url": "https://hub.docker.com",
                     "desc": "镜像仓库", "icon": ""},
                    {"id": new_id("s"), "title": "Cloudflare", "url": "https://dash.cloudflare.com",
                     "desc": "DNS / CDN", "icon": ""},
                ],
            },
        ],
    }


def load_config():
    if not os.path.isfile(CONFIG_PATH):
        cfg = default_config()
        save_config(cfg)
        return cfg
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # 补齐缺省字段，避免老数据缺项炸前端
    base = default_config()
    for k, v in base.items():
        if k not in cfg:
            cfg[k] = v
    # 老数据没有 private 字段，每次读都重算一遍（纯字符串判断，176 个站点耗时可忽略）
    dns = bool(cfg.get("privateDns"))
    for g in cfg.get("groups") or []:
        for s in g.get("sites") or []:
            if "private" not in s or dns:
                s["private"] = is_private_url(str(s.get("url") or ""), dns=dns)
    return cfg


def save_config(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)


HIDDEN_DESC = "内网地址，已隐藏"


def mask_site(site):
    """把内网站点的地址抹掉，只留标题和标记。"""
    out = dict(site)
    out["url"] = ""
    out["desc"] = HIDDEN_DESC
    out["icon"] = ""
    out["masked"] = True
    return out


def public_config(cfg, authed=False):
    """对外输出。

    authed=False（未登录访客）：password 去掉，内网地址按 privateMode 处理
        mask → 卡片还在，url 空、desc 写「内网地址，已隐藏」
        hide → 这些站点整条不下发
        show → 原样（自己内网部署才该用）
    authed=True（后台已登录）：完整配置，内网地址照给
    """
    mode = str(cfg.get("privateMode") or "mask")
    if mode not in ("mask", "hide", "show"):
        mode = "mask"

    out = dict(cfg)
    out.pop("password", None)

    groups, masked, dropped = [], 0, 0
    for g in cfg.get("groups") or []:
        gg = dict(g)
        sites = []
        for s in g.get("sites") or []:
            priv = bool(s.get("private"))
            if not priv or authed or mode == "show":
                sites.append(dict(s))
            elif mode == "hide":
                dropped += 1
            else:
                sites.append(mask_site(s))
                masked += 1
        gg["sites"] = sites
        gg["privateCount"] = sum(1 for s in (g.get("sites") or []) if s.get("private"))
        groups.append(gg)
    out["groups"] = groups
    out["privateMode"] = mode
    out["privateMasked"] = masked
    out["privateDropped"] = dropped
    out["privateTotal"] = sum(1 for g in (cfg.get("groups") or [])
                              for s in (g.get("sites") or []) if s.get("private"))

    # 同步配置里有本机路径，访客不该看到
    if not authed:
        s = dict(cfg.get("sync") or {})
        out["sync"] = {
            "enabled": bool(s.get("enabled")),
            "interval": int(s.get("interval") or 300),
            "mode": s.get("mode") or "merge",
            "lastSync": int(s.get("lastSync") or 0),
        }
    return out


# ─────────────────────── 书签 HTML 解析 ───────────────────────

class BookmarkParser(HTMLParser):
    """解析 Chrome / Edge / Firefox 导出的 Netscape Bookmark 文件。

    结构：<DT><H3>文件夹名</H3><DL><DT><A HREF="...">标题</A>...
    用栈维护当前文件夹路径。
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []          # [(name, [sites])]
        self.root = [("", [])]   # 顶层容器
        self.pending_h3 = None
        self.in_h3 = False
        self.in_a = False
        self.cur_a = None

    # 顶层容器始终在栈底
    def _top(self):
        return self.stack[-1] if self.stack else self.root[0]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "h3":
            self.in_h3 = True
            self.pending_h3 = []
        elif tag == "a":
            href = (a.get("href") or "").strip()
            if not href or href.lower().startswith("javascript:"):
                return
            self.in_a = True
            self.cur_a = {"url": href, "title": [], "icon": a.get("icon") or ""}
        elif tag == "dl":
            # 进入新文件夹（H3 刚结束）或根 DL
            if self.pending_h3 is not None:
                name = "".join(self.pending_h3).strip() or "未命名"
                self.stack.append((name, []))
                self.pending_h3 = None
            else:
                self.stack.append(("", []))
        elif tag == "hr":
            pass

    def handle_endtag(self, tag):
        if tag == "h3":
            self.in_h3 = False
        elif tag == "a" and self.in_a and self.cur_a:
            title = "".join(self.cur_a["title"]).strip() or self.cur_a["url"]
            host = urlparse(self.cur_a["url"]).netloc or self.cur_a["url"][:40]
            folder = self._top()[0]
            self._top()[1].append({
                "title": title,
                "url": self.cur_a["url"],
                "desc": host,
                "icon": "",
                "folder": folder,
            })
            self.in_a = False
            self.cur_a = None
        elif tag == "dl":
            if len(self.stack) > 0:
                name, sites = self.stack.pop()
                if sites or name:
                    self._top()[1].extend(sites)
                    # 记录文件夹名，供上层分组
                    if name:
                        for s in sites:
                            s["folder"] = name if not s["folder"] else s["folder"]

    def handle_data(self, data):
        if self.in_h3 and self.pending_h3 is not None:
            self.pending_h3.append(data)
        elif self.in_a and self.cur_a:
            self.cur_a["title"].append(data)


LAZY_ICON = "https://favicon.im/%s?larger=true"

ROOT_NAMES = {
    "bookmark_bar": "书签栏",
    "other": "其他书签",
    "synced": "移动设备书签",
}


# ─────────────────── 内网 / 外网 地址识别 ───────────────────
#
# 目的：书签里混着路由器、NAS、公司 OA 这类只有在你家/公司网络里才通的地址。
# 一旦导航站挂到公网，这些地址等于把你内网拓扑贴出去。
# 所以导入/保存时先判一遍，标记 private=True，前台默认不下发真实地址。

# 一定算内网的域名后缀（不含点，取最后一段比较）
PRIVATE_TLDS = {
    "local", "localhost", "lan", "internal", "intranet", "intra",
    "corp", "home", "localdomain", "svc", "cluster", "priv", "private",
}

_DNS_CACHE = {}
_DNS_LOCK = threading.Lock()


def _host_of(url):
    try:
        h = urlparse(url).hostname or ""
    except Exception:
        h = ""
    return (h or "").strip().strip(".").lower()


def _ip_private(ip):
    try:
        a = ipaddress.ip_address(ip)
    except Exception:
        return None
    if a.is_loopback or a.is_private or a.is_link_local or a.is_reserved:
        return True
    if a.is_unspecified or a.is_multicast:
        return True
    if a.version == 4:
        # 运营商级 NAT 100.64.0.0/10，和 0.0.0.0/8，标准库的判断各版本不一致，自己补
        if a in ipaddress.ip_network("100.64.0.0/10"):
            return True
        if int(a) >> 24 == 0:
            return True
    # IPv4 映射的 IPv6（::ffff:10.0.0.1）交给对端判断
    if a.version == 6 and a.ipv4_mapped:
        return _ip_private(str(a.ipv4_mapped))
    return False


def _dns_private(host, timeout=0.6):
    """域名看着像公网，但可能解析到内网（公司内网域名）。带缓存，失败就当公网。"""
    with _DNS_LOCK:
        if host in _DNS_CACHE:
            return _DNS_CACHE[host]
    ans = False
    old = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        for info in socket.getaddrinfo(host, None):
            ip = info[4][0]
            if _ip_private(ip):
                ans = True
                break
    except Exception:
        ans = False
    finally:
        socket.setdefaulttimeout(old)
    with _DNS_LOCK:
        _DNS_CACHE[host] = ans
    return ans


def is_private_url(url, dns=False):
    """判断一个地址是否属于内网 / 本机 / 保留地址。

    判定顺序（快 → 慢，任一命中就 True）：
      1. 空协议或者 file: / ftp 到本机
      2. hostname 是 IP 字面量 → 私有段 / 回环 / 链路本地 / 保留段
      3. hostname 是 localhost 或 .local / .lan / .internal 等后缀
      4. hostname 没有点（单标签，如 http://nas/）→ 内网
      5. 可选：DNS 解析后复查（默认关，避免批量导入时被 DNS 拖死）
    """
    low = str(url or "").strip().lower()
    if not low:
        return False
    # 本机 / 局域网共享协议，天生只能内网访问
    if low.startswith(("file://", "smb://", "\\\\")):
        return True

    h = _host_of(low)
    if not h:
        return False

    v = _ip_private(h)
    if v is not None:
        return v

    if h in ("localhost", "localhost.localdomain", "ip6-localhost"):
        return True
    if "." not in h:
        return True          # http://nas/ 、http://router/
    last = h.rsplit(".", 1)[-1]
    if last in PRIVATE_TLDS:
        return True
    if h.endswith(".home.arpa") or h.endswith(".in-addr.arpa"):
        return True
    if dns and _dns_private(h):
        return True
    return False


def mark_site_private(site):
    """给一个站点字典打上 private 标记，返回是否内网。"""
    p = is_private_url(str(site.get("url") or ""))
    site["private"] = bool(p)
    return p


def mark_groups_private(groups):
    n = 0
    for g in groups or []:
        for s in g.get("sites") or []:
            if mark_site_private(s):
                n += 1
    return n


def _mk_site(title, url, desc=""):
    host = ""
    try:
        host = urlparse(url).netloc
    except Exception:
        pass
    return {
        "id": new_id("s"),
        "title": (title or url or "")[:80],
        "url": url,
        "desc": (host or desc or "")[:200],
        "icon": (LAZY_ICON % host) if host else "",
        "private": is_private_url(url),
    }


def _buckets_to_groups(buckets, order):
    groups = []
    for name in order:
        sites = buckets.get(name) or []
        if not sites:
            continue
        groups.append({
            "id": new_id("g"),
            "name": name[:40],
            "icon": "",
            "hidden": False,
            "sites": sites,
        })
    return groups


def parse_bookmarks_html(raw_html):
    """Netscape 书签 HTML → 分组。Chrome / Edge / Firefox 导出格式通用。"""
    p = BookmarkParser()
    p.feed(raw_html)
    p.close()

    buckets = {}
    order = []
    # 已闭合的文件夹会在出栈时把站点并进上层，所以根容器也要算
    for _, sites in list(p.stack) + [p.root[0]]:
        for s in sites:
            g = (s.get("folder") or "").strip() or "书签栏"
            if g not in buckets:
                buckets[g] = []
                order.append(g)
            buckets[g].append(_mk_site(s["title"], s["url"], s.get("desc", "")))
    if not order:
        # 没有文件夹的平铺书签
        flat = [s for _, sites in list(p.stack) + [p.root[0]] for s in sites]
        if flat:
            buckets["书签栏"] = [_mk_site(s["title"], s["url"]) for s in flat]
            order = ["书签栏"]
    return _buckets_to_groups(buckets, order)


def parse_chrome_bookmarks(raw):
    """Chrome 的 Bookmarks JSON → 分组。

    结构：{"roots": {"bookmark_bar": {...}, "other": {...}, "synced": {...}}}
    每个节点 type=folder 有 children，type=url 有 url/name。
    根容器下的直接链接归到根名分组；每个子文件夹独立成组（深一层也拍平进该组）。
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    data = json.loads(raw)
    roots = data.get("roots") or {}

    buckets = {}
    order = []

    def put(group, item):
        key = (group or "书签栏").strip()[:40] or "书签栏"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(_mk_site(item.get("name"), item.get("url", "")))

    def walk(node, group):
        for ch in node.get("children") or []:
            t = ch.get("type")
            if t == "url" and ch.get("url"):
                put(group, ch)
            elif t == "folder":
                walk(ch, (ch.get("name") or "").strip() or group)

    for key in ("bookmark_bar", "other", "synced"):
        node = roots.get(key)
        if isinstance(node, dict):
            walk(node, ROOT_NAMES.get(key, "书签栏"))
    return _buckets_to_groups(buckets, order)


def parse_any(raw):
    """自动识别 Chrome JSON 或 Netscape HTML。"""
    if isinstance(raw, bytes):
        head = raw.lstrip()[:1]
        is_json = head == b"{"
    else:
        is_json = raw.lstrip()[:1] == "{"
    if is_json:
        try:
            groups = parse_chrome_bookmarks(raw)
            if groups:
                return groups
        except Exception:
            pass
    return parse_bookmarks_html(raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else raw)


# ─────────────────────── 书签自动同步 ───────────────────────

SYNC_LOCK = threading.Lock()
SYNC_STATE = {"hash": "", "lastCheck": 0, "lastSync": 0, "lastResult": "", "found": False}


def chrome_default_paths():
    """常见 Chrome / Edge / Chromium profile 里的 Bookmarks 文件位置。"""
    out = []
    if os.name == "nt":
        bases = [os.environ.get("LOCALAPPDATA") or "",
                 os.path.join(os.environ.get("USERPROFILE") or "", "AppData", "Local")]
        for b in bases:
            if not b:
                continue
            out.append(os.path.join(b, "Google", "Chrome", "User Data", "Default", "Bookmarks"))
            out.append(os.path.join(b, "Google", "Chrome Beta", "User Data", "Default", "Bookmarks"))
            out.append(os.path.join(b, "Microsoft", "Edge", "User Data", "Default", "Bookmarks"))
            out.append(os.path.join(b, "Chromium", "User Data", "Default", "Bookmarks"))
    else:
        h = os.path.expanduser("~")
        out += [
            os.path.join(h, ".config", "google-chrome", "Default", "Bookmarks"),
            os.path.join(h, ".config", "google-chrome-beta", "Default", "Bookmarks"),
            os.path.join(h, ".config", "chromium", "Default", "Bookmarks"),
            os.path.join(h, ".config", "microsoft-edge", "Default", "Bookmarks"),
            os.path.join(h, "Library", "Application Support", "Google", "Chrome", "Default", "Bookmarks"),
            os.path.join(h, "Library", "Application Support", "Microsoft Edge", "Default", "Bookmarks"),
        ]
    # docker 常见挂载点
    out += ["/bookmarks/Bookmarks", "/data/Bookmarks", "/chrome/Bookmarks"]
    return out


def display_path(p):
    """把绝对路径折叠成可展示的形式，避免后台界面/错误信息里出现本机目录结构。

    /home/you/.config/google-chrome/Default/Bookmarks  ->  ~/.config/google-chrome/Default/Bookmarks
    <项目>/nav/data/Bookmarks                          ->  ./data/Bookmarks
    其它（比如 C:\\Users\\YOU\\AppData\\...）              ->  ~\\AppData\\... 或 …/Default/Bookmarks
    """
    raw = str(p or "").strip()
    if not raw:
        return ""
    try:
        ap = os.path.abspath(os.path.expanduser(raw))
    except Exception:
        return raw

    def fold(prefix, mark):
        try:
            pre = os.path.abspath(prefix)
        except Exception:
            return None
        if not pre:
            return None
        a, b = ap.lower().replace("/", "\\"), pre.lower().replace("/", "\\")
        if a == b:
            return mark
        if a.startswith(b + "\\"):
            rel = ap[len(pre):].lstrip("\\/").replace("\\", "/")
            return mark + "/" + rel if rel else mark
        return None

    for prefix, mark in ((os.path.expanduser("~"), "~"), (BASE, ".")):
        got = fold(prefix, mark)
        if got:
            return got

    parts = [x for x in raw.replace("\\", "/").split("/") if x]
    if len(parts) > 3:
        return "…/" + "/".join(parts[-2:])
    return raw


def resolve_bookmark_path(cfg):
    s = cfg.get("sync") or {}
    p = (s.get("path") or "").strip()
    if p:
        p = os.path.expanduser(p)
        if os.path.isfile(p):
            return p
        # 传了目录就往下找
        if os.path.isdir(p):
            for name in ("Bookmarks", "bookmarks"):
                q = os.path.join(p, name)
                if os.path.isfile(q):
                    return q
    for c in chrome_default_paths():
        if c and os.path.isfile(c):
            return c
    return p or ""


def merge_groups(existing, incoming, mode="merge"):
    """把同步来的分组并入配置。

    merge  ：同名分组保留 id / icon / hidden / 自定义排序，手动分组也保留
    replace：整站替换，但仍按同名继承 hidden / icon
    """
    old = {}
    for g in existing:
        old.setdefault(g.get("name"), g)

    out = []
    seen = set()
    for g in incoming:
        prev = old.get(g.get("name"))
        g = dict(g)
        g["source"] = "sync"
        if prev:
            g["id"] = prev.get("id") or g["id"]
            g["icon"] = prev.get("icon") or g.get("icon", "")
            g["hidden"] = bool(prev.get("hidden"))
            if prev.get("order") is not None:
                g["order"] = prev.get("order")
        seen.add(g.get("name"))
        out.append(g)

    if mode != "replace":
        for g in existing:
            if g.get("name") not in seen and g.get("source") != "sync":
                out.append(g)
    return out


def sync_once(force=False, path_override=None):
    """跑一次同步。返回 dict，写回 config。"""
    with SYNC_LOCK:
        cfg = load_config()
        sync = cfg.get("sync") or {}
        if path_override:
            sync["path"] = path_override
        p = resolve_bookmark_path(cfg) if not path_override else path_override
        SYNC_STATE["lastCheck"] = int(time.time())

        if not p or not os.path.isfile(p):
            msg = "找不到书签文件：%s" % (display_path(p) or "(未配置，可在后台填 Chrome 的 Bookmarks 路径)")
            sync["lastResult"] = msg
            cfg["sync"] = sync
            save_config(cfg)
            SYNC_STATE["found"] = False
            SYNC_STATE["lastResult"] = msg
            return {"ok": False, "error": msg, "path": p}

        try:
            with open(p, "rb") as f:
                raw = f.read()
        except Exception as e:
            msg = "读取失败：%s" % e
            sync["lastResult"] = msg
            cfg["sync"] = sync
            save_config(cfg)
            SYNC_STATE["lastResult"] = msg
            return {"ok": False, "error": msg, "path": p}

        h = hashlib.sha1(raw).hexdigest()
        if not force and h == SYNC_STATE["hash"]:
            return {"ok": True, "skipped": True, "path": p,
                    "groupsCount": len(cfg.get("groups") or []),
                    "sitesCount": sum(len(g.get("sites") or []) for g in (cfg.get("groups") or []))}

        try:
            incoming = parse_any(raw)
        except Exception as e:
            msg = "解析失败：%s" % e
            sync["lastResult"] = msg
            cfg["sync"] = sync
            save_config(cfg)
            SYNC_STATE["lastResult"] = msg
            return {"ok": False, "error": msg, "path": p}

        if not incoming:
            msg = "文件里没有解析到书签"
            sync["lastResult"] = msg
            cfg["sync"] = sync
            save_config(cfg)
            SYNC_STATE["lastResult"] = msg
            return {"ok": False, "error": msg, "path": p}

        cfg["groups"] = merge_groups(cfg.get("groups") or [], incoming, sync.get("mode") or "merge")
        n_g = len(cfg["groups"])
        n_s = sum(len(g.get("sites") or []) for g in cfg["groups"])
        sync["path"] = p
        sync["lastSync"] = int(time.time())
        sync["lastResult"] = "同步成功：%d 个分组 / %d 个站点" % (len(incoming), sum(len(g["sites"]) for g in incoming))
        cfg["sync"] = sync
        save_config(cfg)

        SYNC_STATE["hash"] = h
        SYNC_STATE["found"] = True
        SYNC_STATE["lastSync"] = sync["lastSync"]
        SYNC_STATE["lastResult"] = sync["lastResult"]
        return {"ok": True, "path": p, "groupsCount": n_g, "sitesCount": n_s,
                "privateCount": sum(1 for g in cfg["groups"]
                                    for s in (g.get("sites") or []) if s.get("private")),
                "syncedGroups": len(incoming), "skipped": False}


def sync_watcher():
    """后台线程：10 秒一拍，按 config 里的 interval 决定这一拍要不要真去读文件。

    这样在后台改间隔立刻生效，不用等上一轮睡完。
    """
    while True:
        try:
            cfg = load_config()
            s = cfg.get("sync") or {}
            if s.get("enabled"):
                iv = max(30, int(s.get("interval") or 300))
                last = int(SYNC_STATE.get("lastCheck") or 0)
                if not last or (time.time() - last) >= iv:
                    sync_once()
        except Exception as e:
            SYNC_STATE["lastResult"] = "同步异常：%s" % e
        time.sleep(10)


# ───────────────────────── HTTP 服务 ─────────────────────────

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json",
}


def issue_token():
    t = secrets.token_urlsafe(24)
    TOKENS[t] = time.time() + TOKEN_TTL
    return t


def token_ok(t):
    exp = TOKENS.get(t)
    if not exp:
        return False
    if exp < time.time():
        TOKENS.pop(t, None)
        return False
    return True


class Handler(BaseHTTPRequestHandler):
    server_version = "AwadaohNav/1.0"
    protocol_version = "HTTP/1.1"

    # ── 工具 ──
    def _send(self, code, body=b"", ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if ctype.startswith("application/json") else "public, max-age=60")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def _err(self, msg, code=400):
        self._json({"ok": False, "error": msg}, code)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return b""
        if n > MAX_BODY:
            raise ValueError("请求体过大")
        return self.rfile.read(n)

    def _auth(self):
        h = self.headers.get("Authorization") or ""
        if h.startswith("Bearer "):
            return token_ok(h[7:].strip())
        return False

    def _static(self, rel):
        rel = rel.lstrip("/") or "index.html"
        path = os.path.normpath(os.path.join(STATIC, rel))
        if not path.startswith(STATIC):
            return self._err("非法路径", 403)
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        if not os.path.isfile(path):
            return self._err("not found", 404)
        ext = os.path.splitext(path)[1].lower()
        with open(path, "rb") as f:
            data = f.read()
        self._send(200, data, MIME.get(ext, "application/octet-stream"))

    # ── 路由 ──
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urlparse(self.path)
        p = unquote(u.path)

        if p in ("/", "/index.html"):
            return self._static("index.html")
        if p in ("/admin", "/admin/", "/admin.html"):
            return self._static("admin.html")

        if p == "/api/config":
            # 带有效 token 就拿完整配置（含内网地址），否则内网地址打码/隐藏
            return self._json({"ok": True, "config": public_config(load_config(), authed=self._auth())})
        if p == "/api/health":
            return self._json({"ok": True, "time": int(time.time())})
        if p == "/api/auth":
            return self._json({"ok": self._auth()})
        if p == "/api/sync":
            if not self._auth():
                return self._err("未登录", 401)
            cfg = load_config()
            s = dict(cfg.get("sync") or {})
            path = resolve_bookmark_path(cfg)
            s["resolvedPath"] = path
            s["pathDisplay"] = display_path(path)
            s["exists"] = bool(path and os.path.isfile(path))
            s["candidates"] = chrome_default_paths()[:6]
            s["state"] = dict(SYNC_STATE)
            if path and os.path.isfile(path):
                try:
                    s["mtime"] = int(os.path.getmtime(path))
                    s["size"] = os.path.getsize(path)
                except Exception:
                    pass
            return self._json({"ok": True, "sync": s})

        return self._static(p)

    def do_POST(self):
        p = urlparse(self.path).path

        if p == "/api/login":
            try:
                data = json.loads(self._body() or b"{}")
            except Exception:
                return self._err("请求格式错误")
            cfg = load_config()
            if not secrets.compare_digest(str(data.get("password", "")), str(cfg.get("password", ""))):
                time.sleep(0.4)  # 简单限速
                return self._err("密码不正确", 401)
            return self._json({"ok": True, "token": issue_token()})

        if p == "/api/import":
            if not self._auth():
                return self._err("未登录", 401)
            raw = self._body()
            if not raw:
                return self._err("没有收到文件内容")
            try:
                groups = parse_any(raw)
            except Exception as e:
                return self._err("解析失败: %s" % e)
            total = sum(len(g["sites"]) for g in groups)
            return self._json({"ok": True, "groups": groups, "groupsCount": len(groups), "sitesCount": total})

        if p == "/api/sync":
            if not self._auth():
                return self._err("未登录", 401)
            try:
                data = json.loads(self._body() or b"{}")
            except Exception:
                data = {}
            cfg = load_config()
            sync = cfg.get("sync") or {}
            if isinstance(data.get("path"), str):
                sync["path"] = data["path"].strip()[:500]
            if isinstance(data.get("mode"), str) and data["mode"] in ("merge", "replace"):
                sync["mode"] = data["mode"]
            if "enabled" in data:
                sync["enabled"] = bool(data["enabled"])
            if isinstance(data.get("interval"), int):
                sync["interval"] = max(30, min(86400, data["interval"]))
            cfg["sync"] = sync
            save_config(cfg)
            res = sync_once(force=True, path_override=sync.get("path") or None)
            res["config"] = public_config(load_config(), authed=True)
            return self._json(res)

        if p == "/api/sync/test":
            if not self._auth():
                return self._err("未登录", 401)
            try:
                data = json.loads(self._body() or b"{}")
            except Exception:
                data = {}
            cfg = load_config()
            sync = dict(cfg.get("sync") or {})
            if isinstance(data.get("path"), str):
                sync["path"] = data["path"].strip()
            tmp = dict(cfg)
            tmp["sync"] = sync
            path = resolve_bookmark_path(tmp)
            if not path or not os.path.isfile(path):
                return self._json({"ok": False, "error": "文件不存在：%s" % (display_path(path) or "(空)"),
                               "resolvedPath": path, "pathDisplay": display_path(path)})
            try:
                with open(path, "rb") as f:
                    groups = parse_any(f.read())
            except Exception as e:
                return self._json({"ok": False, "error": "解析失败：%s" % e, "resolvedPath": path, "pathDisplay": display_path(path)})
            return self._json({"ok": True, "resolvedPath": path, "pathDisplay": display_path(path),
                               "groupsCount": len(groups),
                               "sitesCount": sum(len(g["sites"]) for g in groups),
                               "privateCount": sum(1 for g in groups
                                                   for s in g["sites"] if s.get("private")),
                               "names": [g["name"] for g in groups][:40]})

        return self._err("not found", 404)

    def do_PUT(self):
        p = urlparse(self.path).path
        if p != "/api/config":
            return self._err("not found", 404)
        if not self._auth():
            return self._err("未登录", 401)
        try:
            data = json.loads(self._body() or b"{}")
        except Exception:
            return self._err("请求格式错误")
        cfg = load_config()

        for k in ("title", "subtitle", "footer", "footerUrl", "searchEngine", "theme", "engine"):
            if k in data and isinstance(data[k], str):
                cfg[k] = data[k][:200]

        if data.get("privateMode") in ("mask", "hide", "show"):
            cfg["privateMode"] = data["privateMode"]
        if "privateDns" in data:
            cfg["privateDns"] = bool(data["privateDns"])
        dns = bool(cfg.get("privateDns"))

        if isinstance(data.get("engines"), list):
            engs = []
            for e in data["engines"][:20]:
                if not isinstance(e, dict):
                    continue
                url = str(e.get("url") or "").strip()[:500]
                if not url:
                    continue
                if "%s" not in url:
                    url += "%s"
                engs.append({
                    "id": str(e.get("id") or new_id("e"))[:24],
                    "name": str(e.get("name") or "搜索")[:24],
                    "url": url,
                })
            if engs:
                cfg["engines"] = engs
                ids = [e["id"] for e in engs]
                if cfg.get("engine") not in ids:
                    cfg["engine"] = ids[0]
        if isinstance(data.get("groups"), list):
            clean = []
            for g in data["groups"][:80]:
                if not isinstance(g, dict):
                    continue
                sites = []
                for s in (g.get("sites") or [])[:500]:
                    if not isinstance(s, dict) or not s.get("url"):
                        continue
                    u = str(s.get("url"))[:2000]
                    sites.append({
                        "id": s.get("id") or new_id("s"),
                        "title": str(s.get("title") or "")[:80],
                        "url": u,
                        "desc": str(s.get("desc") or "")[:200],
                        "icon": str(s.get("icon") or "")[:500],
                        # 每次保存都重算，改了地址立刻跟上
                        "private": is_private_url(u, dns=dns),
                    })
                clean.append({
                    "id": g.get("id") or new_id("g"),
                    "name": str(g.get("name") or "未命名")[:40],
                    "icon": str(g.get("icon") or "")[:8],
                    "hidden": bool(g.get("hidden")),
                    "source": str(g.get("source") or "")[:12],
                    "sites": sites,
                })
            cfg["groups"] = clean

        # 同步设置
        if isinstance(data.get("sync"), dict):
            cur = cfg.get("sync") or {}
            sd = data["sync"]
            if "enabled" in sd:
                cur["enabled"] = bool(sd["enabled"])
            if isinstance(sd.get("path"), str):
                cur["path"] = sd["path"].strip()[:500]
            if isinstance(sd.get("interval"), int):
                cur["interval"] = max(30, min(86400, sd["interval"]))
            if sd.get("mode") in ("merge", "replace"):
                cur["mode"] = sd["mode"]
            cfg["sync"] = cur

        # 改密码（可选）
        np = data.get("newPassword")
        if isinstance(np, str) and len(np) >= 4:
            cfg["password"] = np[:64]

        save_config(cfg)
        return self._json({"ok": True, "config": public_config(cfg, authed=True)})

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "3055"))
    os.makedirs(DATA_DIR, exist_ok=True)
    cfg = load_config()

    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True

    t = threading.Thread(target=sync_watcher, name="sync-watcher", daemon=True)
    t.start()

    sync = cfg.get("sync") or {}
    resolved = resolve_bookmark_path(cfg)
    n_priv = sum(1 for g in (cfg.get("groups") or [])
                 for s in (g.get("sites") or []) if s.get("private"))
    mode_label = {"mask": "打码", "hide": "不显示", "show": "正常显示"}.get(
        str(cfg.get("privateMode") or "mask"), "打码")

    print("=" * 56)
    print("  Awadaoh Nav")
    print("  前台  http://%s:%d/" % ("127.0.0.1" if host == "0.0.0.0" else host, port))
    print("  后台  http://%s:%d/admin" % ("127.0.0.1" if host == "0.0.0.0" else host, port))
    print("  密码  %s" % cfg.get("password"))
    print("  数据  %s" % CONFIG_PATH)
    print("  同步  %s  %s" % ("开启" if sync.get("enabled") else "关闭",
                             resolved or "(未找到 Bookmarks 文件)"))
    print("  内网  %d 个地址，访客视图 %s" % (n_priv, mode_label))
    print("=" * 56)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
