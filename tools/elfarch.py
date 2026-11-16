#!/usr/bin/env python3
"""Awadaoh · 读 ELF 头判断二进制真实架构

为什么需要这个：镜像的「架构标签」和「里面的二进制」是两件独立的事。
buildx 打 `linux/arm64` 标签时只会做三件事——写 manifest 的 platform 字段、
把 TARGETARCH 注入 Dockerfile、给 RUN 挂 qemu。它**不会**检查你 COPY 进去的
文件到底是哪个架构的。所以只要 pro/arm64/awadaoh 里躺着一个 amd64 二进制，
CI 一样绿灯，镜像一样能推，用户 `docker compose up` 之后才开始
`exec format error` 无限重启。

用法：
  python3 tools/elfarch.py pro/arm64/awadaoh                 # 只打印
  python3 tools/elfarch.py pro/arm64/awadaoh --expect arm64   # 不符则 exit 1
  python3 tools/elfarch.py pro/amd64/awadaoh pro/arm64/awadaoh --expect-each
"""
import sys
import struct
import os

# e_machine -> docker 架构名
MACHINES = {
    0x03: "386",
    0x08: "mips",
    0x14: "ppc",
    0x15: "ppc64",
    0x16: "s390x",
    0x28: "arm",
    0x2A: "superh",
    0x32: "ia64",
    0x3E: "amd64",
    0xB7: "arm64",
    0xF3: "riscv",
}


def read_arch(path):
    """返回 (arch, detail)。非 ELF 返回 ("unknown", 原因)。"""
    try:
        with open(path, "rb") as f:
            head = f.read(64)
    except OSError as e:
        return "missing", str(e)

    if len(head) < 20 or head[:4] != b"\x7fELF":
        magic = head[:4]
        return "unknown", "不是 ELF（magic=%r），可能是 Mach-O / PE / 空文件" % magic

    ei_class = head[4]
    ei_data = head[5]
    if ei_data == 1:
        endian = "<"
    elif ei_data == 2:
        endian = ">"
    else:
        return "unknown", "ELF 字节序字段非法: %d" % ei_data

    machine = struct.unpack(endian + "H", head[18:20])[0]
    arch = MACHINES.get(machine, "elf-0x%02x" % machine)
    bits = {1: 32, 2: 64}.get(ei_class, "?")
    return arch, "%s/%s-bit" % (endian == "<" and "LE" or "BE", bits)


def check(path, expect):
    arch, detail = read_arch(path)
    size = os.path.getsize(path) if os.path.exists(path) else -1
    print("  %-28s %-10s (%s, %d B)" % (path, arch, detail, size))
    if expect and arch != expect:
        print(
            "  !! 架构不符：期望 %s，实际 %s。这个文件打进镜像后必然 "
            "`exec format error`。" % (expect, arch)
        )
        return False
    return True


def main(argv):
    expect = None
    expect_each = False
    paths = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--expect":
            i += 1
            expect = argv[i]
        elif a.startswith("--expect="):
            expect = a.split("=", 1)[1]
        elif a == "--expect-each":
            expect_each = True
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            paths.append(a)
        i += 1

    if not paths:
        print(__doc__)
        return 2

    ok = True
    for p in paths:
        exp = None
        if expect_each:
            # pro/arm64/awadaoh -> arm64；也接受文件名里带 amd64/arm64
            low = p.replace("\\", "/").lower()
            for cand in ("arm64", "amd64"):
                if "/%s/" % cand in low or low.endswith("_%s" % cand):
                    exp = cand
                    break
        else:
            exp = expect
        ok = check(p, exp) and ok

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
