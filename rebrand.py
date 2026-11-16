#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AKKdaoh 品牌替换：把上游 akkdaoh 的标识替换成本项目标识。
跳过 LICENSE（MIT 要求保留原版权声明）。"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP_FILES = {
    "LICENSE", "pnpm-lock.yaml", "package-lock.json",
    "README.md", "UPDATELOG.md", "doc/donate.md",
}
SKIP_DIRS = {".git", "node_modules", "dist", ".github"}

RULES = [
    # 长的先替换，避免被短规则截断
    ("awahello.github.io/akkdaoh-tool-page", "awahello.github.io/akkdaoh-tool-page"),
    ("awahello/akkdaoh", "awahello/akkdaoh"),
    ("awahello/akkdaoh", "awahello/akkdaoh"),
    ("pro.akkdaoh.local", "pro.akkdaoh.local"),
    ("akkdaoh.local/doc", "akkdaoh.local/doc"),
    ("Akkdaoh", "Akkdaoh"),
    ("akkdaoh", "akkdaoh"),
]


def process(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except (UnicodeDecodeError, OSError):
        return 0
    out = src
    hits = 0
    for old, new in RULES:
        if old in out:
            hits += out.count(old)
            out = out.replace(old, new)
    if out != src:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(out)
    return hits


def main():
    total = 0
    files = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            if rel in SKIP_FILES:
                continue
            if name.endswith((".png", ".jpg", ".ico", ".woff", ".woff2", ".ttf")):
                continue
            n = process(full)
            if n:
                total += n
                files += 1
                print("  %-55s %d" % (rel, n))
    print("\n替换 %d 处，涉及 %d 个文件" % (total, files))


if __name__ == "__main__":
    sys.exit(main())
