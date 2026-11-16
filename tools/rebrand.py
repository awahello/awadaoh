#!/usr/bin/env python3
"""Awadaoh · 抹掉上游品牌（后端二进制 + 前端包）

两条线，两种做法，原因不同：

1) 后端二进制（`--bin`）
   PRO 授权判定（ProIsExpired）只存在于上游 release 的预编译二进制里，
   公开源码树里没有这段代码，所以我们没法自己 build 出带 PRO 的二进制，
   只能在上游二进制上打字节补丁。
   Go 把字符串常量存成 (指针, 长度) 两段，长度烘在指令流里。
   改短了字符串内容但不改长度 → 打印出来带 NUL 或错位。
   所以这里**只做等长替换**：每条规则都断言 len(old) == len(new)。
   长短不一时请把整句一起换，别只换品牌名。

2) 前端包（`--web`）
   纯文本文件（html/js/css），随便改长度，直接换。

用法：
  python3 tools/rebrand.py --bin pro/arm64/awadaoh
  python3 tools/rebrand.py --web pro/web
  python3 tools/rebrand.py --bin pro/arm64/awadaoh --web pro/web --check
"""
import argparse
import os
import sys

# ── 后端二进制：必须等长 ──────────────────────────────────────────
# (old, new, 是否必须命中)
BIN_RULES = [
    # 启动横幅
    (b"Welcome to the Sun-Panel.", b"Welcome to Awadaoh Panel!"),
    (b"Sun-Panel is Started.", b"Awadaoh is started up"),
    # 启动时打印的项目地址
    (b"https://github.com/hslr-s/sun-panel", b"https://github.com/awahello/awadaoh"),
    # 备份文件名前缀
    (b"Sun-Panel Backup", b"Awadaoh Backup  "),
]

# 兜底：把剩下的独立 Sun-Panel 换成 Awadaoh + 两个空格（补足 9 字节）。
# Sun-Panel_backup_v1 / _v2 是历史备份目录名，改了会让老备份找不到，跳过。
BIN_FALLBACK_OLD = b"Sun-Panel"
BIN_FALLBACK_NEW = b"Awadaoh  "
BIN_FALLBACK_SKIP = (b"Sun-Panel_backup_v1", b"Sun-Panel_backup_v2")

# ── 前端包：随便改长度，但顺序要从长到短 ────────────────────────
WEB_RULES = [
    (b"Sun-Panel.Top", b"Awadaoh"),
    (b"hslr-s/sun-panel", b"awahello/awadaoh"),
    (b"Sun-Panel", b"Awadaoh"),
]

WEB_EXTS = (".html", ".htm", ".js", ".mjs", ".css", ".json", ".svg", ".txt", ".map")


def patch_bin(path, check_only=False):
    with open(path, "rb") as f:
        data = f.read()
    orig = data
    report = []

    for old, new in BIN_RULES:
        assert len(old) == len(new), "等长规则被破坏: %r -> %r" % (old, new)
        n = data.count(old)
        report.append((old, new, n))
        if n:
            data = data.replace(old, new)

    # 兜底：逐个扫，跳过备份目录名
    out = bytearray()
    i = 0
    skipped = 0
    hits = 0
    while True:
        j = data.find(BIN_FALLBACK_OLD, i)
        if j < 0:
            out += data[i:]
            break
        tail = data[j:j + len(BIN_FALLBACK_SKIP[0])]
        if tail in BIN_FALLBACK_SKIP:
            out += data[i:j + len(BIN_FALLBACK_OLD)]
            i = j + len(BIN_FALLBACK_OLD)
            skipped += 1
            continue
        out += data[i:j]
        out += BIN_FALLBACK_NEW
        i = j + len(BIN_FALLBACK_OLD)
        hits += 1
    data = bytes(out)
    report.append((BIN_FALLBACK_OLD, BIN_FALLBACK_NEW, hits))

    # 复核：不能还有裸 Sun-Panel（备份目录名除外）
    leftover = 0
    k = 0
    while True:
        j = data.find(BIN_FALLBACK_OLD, k)
        if j < 0:
            break
        if data[j:j + len(BIN_FALLBACK_SKIP[0])] in BIN_FALLBACK_SKIP:
            k = j + len(BIN_FALLBACK_OLD)
            continue
        leftover += 1
        k = j + len(BIN_FALLBACK_OLD)

    print("== 后端二进制: %s" % path)
    for old, new, n in report:
        # --check 是复核已打过补丁的文件，命中 0 次才是对的，别标成异常
        flag = "  " if (n or check_only) else "??"
        print("  %s %-38r -> %-38r x%d" % (flag, old, new, n))
    print("  跳过（历史备份目录名）: %d" % skipped)
    print("  残留 Sun-Panel: %d" % leftover)

    if leftover:
        print("  !! 还有 %d 处没换掉，品牌会漏" % leftover)
        return False
    if check_only:
        return True
    if data != orig:
        with open(path, "wb") as f:
            f.write(data)
        print("  已写回 %s (%d B)" % (path, len(data)))
    else:
        print("  无需改动")
    return True


def patch_web(root, check_only=False):
    if not os.path.isdir(root):
        print("!! 目录不存在: %s" % root)
        return False

    total = 0
    touched = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if not name.lower().endswith(WEB_EXTS):
                continue
            # 跳过 macOS 的 AppleDouble 垃圾
            if name.startswith("._"):
                continue
            p = os.path.join(dirpath, name)
            try:
                with open(p, "rb") as f:
                    data = f.read()
            except OSError:
                continue
            new = data
            for old, rep in WEB_RULES:
                if old in new:
                    new = new.replace(old, rep)
            if new != data:
                touched += 1
                cnt = sum(data.count(o) for o, _ in WEB_RULES)
                total += cnt
                print("  %-60s %d 处" % (os.path.relpath(p, root), cnt))
                if not check_only:
                    with open(p, "wb") as f:
                        f.write(new)

    print("== 前端包: %s  改动文件 %d 个，替换 %d 处" % (root, touched, total))

    # 复核：不许还有可见品牌
    left = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if not name.lower().endswith(WEB_EXTS) or name.startswith("._"):
                continue
            p = os.path.join(dirpath, name)
            try:
                with open(p, "rb") as f:
                    d = f.read()
            except OSError:
                continue
            if b"Sun-Panel" in d or b"hslr-s/sun-panel" in d:
                left.append(os.path.relpath(p, root))
    if left:
        print("  !! 仍有品牌残留: %s" % ", ".join(left[:5]))
        return False
    print("  残留 Sun-Panel: 0")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", action="append", default=[], help="后端二进制，可多次")
    ap.add_argument("--web", action="append", default=[], help="前端目录，可多次")
    ap.add_argument("--check", action="store_true", help="只检查/复核，不写")
    args = ap.parse_args()

    if not args.bin and not args.web:
        ap.print_help()
        return 2

    ok = True
    for p in args.bin:
        ok = patch_bin(p, args.check) and ok
    for p in args.web:
        ok = patch_web(p, args.check) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
