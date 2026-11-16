#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Awadaoh · 官方 web 包视觉注入

作用：
  1. 把 assets/theme/nav-theme.css 放进 web 根，并在 index.html </head> 前插入
     <link rel="stylesheet" href="/awadaoh-theme.css">，保证排在官方 CSS 之后。
  2. 用本项目的 logo / favicon 覆盖官方同名文件。
  3. 清掉 index.html 里残留的上游标题注释。

不改 JS、不改 DOM、不改接口，纯静态资源替换，可重复执行（幂等）。

用法：
    python web-inject.py <web目录>
    python web-inject.py <web目录> --check     # 只检查，不改
    python web-inject.py <web目录> --revert    # 从 .bak 还原 index.html
"""

import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME_SRC = os.path.join(ROOT, "assets", "theme", "nav-theme.css")
THEME_NAME = "awadaoh-theme.css"
LINK_TAG = '<link rel="stylesheet" href="/%s">' % THEME_NAME
CATNAV_SRC = os.path.join(ROOT, "assets", "theme", "catnav.js")
CATNAV_REL = os.path.join("custom", "index.js")

# 官方 index.html 中需要就地替换的上游痕迹
HTML_REPLACEMENTS = [
    ("<!-- <title>Sun-Panel</title> -->", "<!-- Awadaoh -->"),
    ("<title>Sun-Panel</title>", "<title>Awadaoh</title>"),
    ("Sun-Panel", "Awadaoh"),  # 兜底：任何残留的可见文案
]

# 用本项目资源覆盖官方同名文件
ASSET_SOURCES = [
    ("public/logo.png", "logo.png"),
    ("public/favicon.ico", "favicon.ico"),
    ("public/favicon.svg", "favicon.svg"),
    ("public/favicon-black.svg", "favicon-black.svg"),
]


def log(msg):
    print("  " + msg)


def inject_html(web_dir):
    idx = os.path.join(web_dir, "index.html")
    if not os.path.isfile(idx):
        raise SystemExit("找不到 %s" % idx)

    with open(idx, "r", encoding="utf-8") as f:
        html = f.read()

    changed = []

    for old, new in HTML_REPLACEMENTS:
        if old in html:
            html = html.replace(old, new)
            changed.append("文案: %s" % old[:40])

    if LINK_TAG not in html:
        if "</head>" not in html:
            raise SystemExit("index.html 里没有 </head>，无法注入")
        html = html.replace("</head>", "\t" + LINK_TAG + "\n</head>", 1)
        changed.append("注入主题样式表")

    if not changed:
        log("index.html 无需改动")
        return False

    bak = idx + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(idx, bak)

    with open(idx, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    for c in changed:
        log(c)
    return True


def copy_theme(web_dir):
    if not os.path.isfile(THEME_SRC):
        raise SystemExit("找不到主题文件 %s" % THEME_SRC)
    dst = os.path.join(web_dir, THEME_NAME)
    shutil.copy2(THEME_SRC, dst)
    log("主题 -> %s (%.1f KB)" % (THEME_NAME, os.path.getsize(dst) / 1024.0))


def copy_catnav(web_dir):
    """左侧分类导航：写进官方预留的 /custom/index.js 扩展点。"""
    if not os.path.isfile(CATNAV_SRC):
        raise SystemExit("找不到分类导航脚本 %s" % CATNAV_SRC)
    dst = os.path.join(web_dir, CATNAV_REL)
    d = os.path.dirname(dst)
    if not os.path.isdir(d):
        os.makedirs(d)
    bak = dst + ".bak"
    if os.path.isfile(dst) and not os.path.exists(bak):
        shutil.copy2(dst, bak)
    shutil.copy2(CATNAV_SRC, dst)
    log("分类导航 -> %s (%.1f KB)" % (CATNAV_REL.replace(os.sep, "/"),
                                     os.path.getsize(dst) / 1024.0))


def copy_assets(web_dir):
    for rel, name in ASSET_SOURCES:
        src = os.path.join(ROOT, rel)
        if not os.path.isfile(src):
            log("跳过缺失资源 %s" % rel)
            continue
        dst = os.path.join(web_dir, name)
        bak = dst + ".bak"
        if os.path.exists(dst) and not os.path.exists(bak):
            shutil.copy2(dst, bak)
        shutil.copy2(src, dst)
        log("覆盖 %s (%.1f KB)" % (name, os.path.getsize(dst) / 1024.0))


def check(web_dir):
    idx = os.path.join(web_dir, "index.html")
    ok = True

    if os.path.isfile(os.path.join(web_dir, THEME_NAME)):
        log("[OK] %s 已就位" % THEME_NAME)
    else:
        log("[缺失] %s" % THEME_NAME)
        ok = False

    if os.path.isfile(os.path.join(web_dir, CATNAV_REL)):
        log("[OK] custom/index.js 分类导航已就位")
    else:
        log("[缺失] custom/index.js")
        ok = False

    if os.path.isfile(idx):
        with open(idx, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        if LINK_TAG in html:
            log("[OK] index.html 已引用主题")
        else:
            log("[缺失] index.html 未引用主题")
            ok = False
        if "Sun-Panel" in html:
            log("[残留] index.html 仍含 Sun-Panel 字样")
            ok = False
        else:
            log("[OK] index.html 无上游标题")
    return ok


def revert(web_dir):
    idx = os.path.join(web_dir, "index.html")
    bak = idx + ".bak"
    if os.path.isfile(bak):
        shutil.copy2(bak, idx)
        log("index.html 已还原")
    else:
        log("没有 index.html.bak，跳过")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("web_dir")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()

    web = a.web_dir
    if not os.path.isdir(web):
        raise SystemExit("不是目录: %s" % web)

    if a.check:
        sys.exit(0 if check(web) else 1)

    if a.revert:
        revert(web)
        return

    copy_theme(web)
    copy_catnav(web)
    copy_assets(web)
    inject_html(web)
    print()
    print("注入完成。")
    check(web)


if __name__ == "__main__":
    main()
