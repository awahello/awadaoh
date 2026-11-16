#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Awadaoh · 前端 PRO 标识解锁补丁

官方 PRO 版前端在 micro-app 宿主里这样算 isPro：

    mainAppInfo:{get:async()=>{
        const [n,h] = await Promise.all([Do(), ka()])
        const k = { version: ..., isPro: h.data ? !h.data.isExpired : false }
        return k
    }}

把 `h.data ? !h.data.isExpired : false` 换成 `!0`，micro app 一律按 PRO 处理，
避免后端已放行而前端仍显示"未授权"。压缩后的变量名会随版本变化，用正则匹配。

用法：
    python patch-web.py <web目录>          # 打补丁
    python patch-web.py <web目录> --check  # 只检查
"""
import os
import re
import sys

# isPro:X.data?!X.data.isExpired:!1   /  isPro:!!X.data
PATTERN = re.compile(rb"isPro:([A-Za-z_$][\w$]*)\.data\?!\1\.data\.isExpired:!1")
PATTERN2 = re.compile(rb"isPro:!!([A-Za-z_$][\w$]*)\.data")
REPL = b"isPro:!0"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    web = sys.argv[1]
    check_only = "--check" in sys.argv

    if not os.path.isdir(web):
        print("not a directory: %s" % web)
        return 2

    total = 0
    for dirpath, _, files in os.walk(web):
        for name in files:
            if not name.endswith(".js"):
                continue
            full = os.path.join(dirpath, name)
            data = open(full, "rb").read()
            new, n1 = PATTERN.subn(REPL, data)
            new, n2 = PATTERN2.subn(REPL, new)
            n = n1 + n2
            if n:
                rel = os.path.relpath(full, web)
                print("  %-46s %d 处" % (rel, n))
                total += n
                if not check_only:
                    open(full, "wb").write(new)

    if not total:
        # 已经打过或版本差异
        already = any(b"isPro:!0" in open(os.path.join(d, f), "rb").read()
                      for d, _, fs in os.walk(web) for f in fs if f.endswith(".js"))
        print("未找到待替换片段；%s" % ("疑似已打过补丁" if already else "版本可能已变化，请人工确认"))
        return 0 if already else 3

    print("\n共处理 %d 处%s" % (total, "" if check_only else "（已写入）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
