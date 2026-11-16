#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""极简 ELF64 符号表读取器 + 函数字节 patch 工具（无第三方依赖）。

用法:
  python elfsym.py list  <binary> [关键字...]      列出匹配符号
  python elfsym.py hex   <binary> <符号名> [字节数] 打印函数头部机器码
  python elfsym.py patch <binary> <符号名> <hex>    用 hex 覆盖函数入口
"""
import struct
import sys


class ELF:
    def __init__(self, path):
        self.path = path
        self.data = bytearray(open(path, "rb").read())
        d = self.data
        assert d[:4] == b"\x7fELF", "not an ELF"
        self.is64 = d[4] == 2
        assert self.is64, "only ELF64 supported"
        self.le = d[5] == 1
        e = "<" if self.le else ">"
        (self.e_type, self.e_machine, _, self.e_entry, self.e_phoff,
         self.e_shoff, _, _, self.e_phentsize, self.e_phnum,
         self.e_shentsize, self.e_shnum, self.e_shstrndx) = struct.unpack_from(
            e + "HHIQQQIHHHHHH", d, 16)
        self.end = e
        self.sections = self._sections()

    def _sections(self):
        d, e, out = self.data, self.end, []
        shstr = None
        for i in range(self.e_shnum):
            off = self.e_shoff + i * self.e_shentsize
            name, typ, flags, addr, offset, size, link, info, align, entsize = \
                struct.unpack_from(e + "IIQQQQIIQQ", d, off)
            out.append(dict(name_off=name, type=typ, flags=flags, addr=addr,
                            offset=offset, size=size, link=link,
                            entsize=entsize))
        if self.e_shstrndx < len(out):
            shstr = out[self.e_shstrndx]
        if shstr:
            base = shstr["offset"]
            for s in out:
                start = base + s["name_off"]
                stop = d.find(b"\x00", start)
                s["name"] = d[start:stop].decode("utf-8", "replace")
        return out

    def seg_offset(self, vaddr):
        """虚拟地址 -> 文件偏移。"""
        d, e = self.data, self.end
        for i in range(self.e_phnum):
            off = self.e_phoff + i * self.e_phentsize
            p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = \
                struct.unpack_from(e + "IIQQQQQQ", d, off)
            if p_type == 1 and p_vaddr <= vaddr < p_vaddr + p_filesz:
                return p_offset + (vaddr - p_vaddr)
        return None

    def symbols(self):
        symtab = next((s for s in self.sections if s.get("name") == ".symtab"), None)
        strtab = next((s for s in self.sections if s.get("name") == ".strtab"), None)
        if not symtab or not strtab:
            return []
        d, e = self.data, self.end
        base = strtab["offset"]
        out = []
        n = symtab["size"] // 24
        for i in range(n):
            off = symtab["offset"] + i * 24
            st_name, st_info, st_other, st_shndx, st_value, st_size = \
                struct.unpack_from(e + "IBBHQQ", d, off)
            if not st_name:
                continue
            start = base + st_name
            stop = d.find(b"\x00", start)
            name = d[start:stop].decode("utf-8", "replace")
            out.append((name, st_value, st_size, st_info))
        return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    cmd, path = sys.argv[1], sys.argv[2]
    elf = ELF(path)

    if cmd == "list":
        keys = [k.lower() for k in sys.argv[3:]] or [""]
        for name, value, size, info in elf.symbols():
            low = name.lower()
            if any(k in low for k in keys):
                kind = "T" if (info & 0xF) in (1, 2) else "?"
                print("%s %016x %6d  %s" % (kind, value, size, name))
        return 0

    if cmd == "hex":
        target = sys.argv[3]
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 64
        for name, value, size, info in elf.symbols():
            if name == target:
                off = elf.seg_offset(value)
                print("vaddr=%#x off=%#x size=%d" % (value, off, size))
                print(elf.data[off:off + n].hex(" ", 4))
                return 0
        print("symbol not found")
        return 2

    if cmd == "patch":
        target = sys.argv[3]
        payload = bytes.fromhex(sys.argv[4].replace(" ", ""))
        for name, value, size, info in elf.symbols():
            if name == target:
                off = elf.seg_offset(value)
                if off is None:
                    print("cannot map vaddr")
                    return 3
                old = bytes(elf.data[off:off + len(payload)])
                elf.data[off:off + len(payload)] = payload
                open(path, "wb").write(elf.data)
                print("patched %s @ %#x" % (target, off))
                print("old:", old.hex(" "))
                print("new:", payload.hex(" "))
                return 0
        print("symbol not found")
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
