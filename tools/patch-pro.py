#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Awadaoh · PRO 授权解锁补丁

作用对象：官方 sun-panel PRO 版 Linux 二进制（release tar.gz 里的 sun-panel）。
原理：
    sun-panel/biz.(*ProAuthType).ProIsExpired  是全局唯一的 PRO 权限判定，
    被 13 处调用（GetSiteSetting / Docker 操作 / 备份恢复 / 自定义 JS-CSS /
    公共图库上传 / micro app 数量限制 / openness 开放接口 …）。
    把函数入口改成 `mov w0,#0 ; ret`，即恒定返回 false（未过期），
    PRO 判定全部放行。TempAuthIsExpired（临时登录态续期）不动。

用法：
    python patch-pro.py /path/to/sun-panel              # 打补丁（自动备份 .orig）
    python patch-pro.py /path/to/sun-panel --check      # 只检查是否已打
    python patch-pro.py /path/to/sun-panel --revert     # 从 .orig 还原

支持架构：linux/arm64、linux/amd64（两种都换算成同一组指令字节）
"""
import os
import shutil
import struct
import sys
import bisect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from elfsym import ELF  # noqa: E402

TARGET = "sun-panel/biz.(*ProAuthType).ProIsExpired"

# arm64: mov w0, #0 ; ret
ARM64_STUB = bytes.fromhex("00008052" "c0035fd6")
# amd64: xor eax, eax ; ret
AMD64_STUB = bytes.fromhex("31c0" "c3")

MACHINE_ARM64 = 183
MACHINE_AMD64 = 62


def find_symbol(elf, name):
    for n, v, s, info in elf.symbols():
        if n == name:
            return v, s
    return None, None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "--patch"
    orig = path + ".orig"

    if mode == "--revert":
        if not os.path.exists(orig):
            print("没有备份文件 %s" % orig)
            return 2
        shutil.copyfile(orig, path)
        print("已还原: %s <- %s" % (path, orig))
        return 0

    elf = ELF(path)
    stub = ARM64_STUB if elf.e_machine == MACHINE_ARM64 else AMD64_STUB
    vaddr, size = find_symbol(elf, TARGET)
    if vaddr is None:
        print("找不到符号 %s" % TARGET)
        print("→ 该二进制可能已被 strip，或不是 PRO 版")
        return 3

    off = elf.seg_offset(vaddr)
    cur = bytes(elf.data[off:off + len(stub)])
    patched = cur == stub

    print("文件     : %s" % path)
    print("架构     : %s" % ("arm64" if elf.e_machine == MACHINE_ARM64 else "amd64"))
    print("符号     : %s" % TARGET)
    print("vaddr    : %#x  文件偏移: %#x  函数长度: %d" % (vaddr, off, size))
    print("当前字节 : %s" % cur.hex(" "))
    print("补丁字节 : %s" % stub.hex(" "))
    print("状态     : %s" % ("已打过补丁" if patched else "原始"))

    if mode == "--check":
        return 0 if patched else 1
    if patched:
        print("无需重复打补丁。")
        return 0

    if not os.path.exists(orig):
        shutil.copyfile(path, orig)
        print("已备份   : %s" % orig)

    elf.data[off:off + len(stub)] = stub
    with open(path, "wb") as f:
        f.write(elf.data)

    # 复核
    with open(path, "rb") as f:
        f.seek(off)
        assert f.read(len(stub)) == stub
    st = os.stat(path)
    os.chmod(path, st.st_mode | 0o111)
    print("完成     : ProIsExpired 现在恒定返回 false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
