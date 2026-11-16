#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Awadaoh 品牌替换：把上游 sun-panel 的标识替换成本项目标识。

用法：
    python3 rebrand.py            # 就地替换
    python3 rebrand.py --check    # 只报告残留，不写文件（CI / 提交前自检）
    python3 rebrand.py --root DIR # 指定要处理的目录（默认脚本所在目录）

跳过 LICENSE（MIT 要求保留原版权声明）、lock 文件、二进制资源。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

SKIP_FILES = {
    "LICENSE",
    "pnpm-lock.yaml",
    "package-lock.json",
    # 说明性文档，保留上游出处
    "README.md",
    "UPDATELOG.md",
    "doc/donate.md",
    "rebrand.py",
}
SKIP_DIRS = {".git", "node_modules", "dist", ".shots", "__pycache__",
             # 构建产物与工具脚本：里面有上游 release 名/下载地址，是有意保留的
             "pro", "tools"}

# 有意保留的内部标识（不是展示文案，改了就断兼容）
ALLOW = {
    # 数据库名 / 表前缀，改名会让老库失联
    "service/assets/conf.example.ini": {"sun_panel"},
    # 旧版导出文件的兼容后缀
    "src/components/apps/ImportExport/index.vue": {"sunpanel"},
    # CSS 类名
    "src/components/common/ItemCard/index.vue": {"sunpanel"},
    "src/views/home/components/AppIcon/index.vue": {"sunpanel"},
    # 上游 release 包名 / Go 符号路径，必须逐字保留
    "Dockerfile.pro": {"sun-panel_", "sun-panel"},
    "doc/PRO.md": {"sun-panel_", "sun-panel"},
}
SKIP_EXT = (".png", ".jpg", ".jpeg", ".webp", ".ico", ".gif",
            ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".zip", ".gz", ".tar")

# 长的先替换，避免被短规则截断
RULES = [
    # 仓库 / 主页 / 文档站
    ("hslr-s/sun-panel", "awahello/awadaoh"),
    ("sun-panel.hslr.site", "www.akkdiy.cn"),
    ("awahello.github.io/sun-panel", "awahello.github.io/awadaoh"),
    # 制品名 / 包名 / 文件名
    ("sun-panel_", "awadaoh_"),
    ("sun-panel.", "awadaoh."),
    ("sun-panel-", "awadaoh-"),
    ("sun_panel", "awadaoh"),
    # 可见品牌
    ("SunPanel", "Awadaoh"),
    ("Sun-Panel", "Awadaoh"),
    ("Sun Panel", "Awadaoh"),
    ("SUN-PANEL", "AWADAOH"),
    # 旧命名兜底
    ("AKKdaoh", "Awadaoh"),
    ("Akkdaoh", "Awadaoh"),
    # 小写兜底放最后
    ("sun-panel", "awadaoh"),
    ("sunpanel", "awadaoh"),
    ("akkdaoh", "awadaoh"),
]


def process(path, rel, check):
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except (UnicodeDecodeError, OSError):
        return 0, {}
    allow = ALLOW.get(rel, set())
    out = src
    hits = {}
    for old, new in RULES:
        if old in allow:
            continue
        n = out.count(old)
        if n:
            hits[old] = hits.get(old, 0) + n
            out = out.replace(old, new)
    total = sum(hits.values())
    if not check and out != src:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(out)
    return total, hits


def main(argv):
    check = "--check" in argv
    root = ROOT
    if "--root" in argv:
        root = os.path.abspath(argv[argv.index("--root") + 1])

    total = files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(SKIP_EXT):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            if rel in SKIP_FILES:
                continue
            n, hits = process(full, rel, check)
            if n:
                total += n
                files += 1
                detail = ", ".join("%s×%d" % (k, v) for k, v in hits.items())
                print("  %-55s %-3d %s" % (rel, n, detail) if check else "  %-55s %d" % (rel, n))

    verb = "待替换" if check else "替换"
    print("\n%s %d 处，涉及 %d 个文件" % (verb, total, files))
    if check and total:
        print("!! 仍有上游/旧名残留，跑一遍 python3 rebrand.py 清理")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
