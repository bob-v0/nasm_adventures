"""Level 15: the game's module (copied to 0x80000) calls printk with formats and
arguments, the C way, and hexdump on some bytes; Python works out what must come out."""

import functools
import re

MOD = 0x80000


def fmt_one(spec, arg):
    m = re.fullmatch(r"%(-?)(0?)(\d*)([duxpsc%])", spec)
    left, zero, width, conv = m.groups()
    width = int(width or 0)
    if isinstance(arg, int):
        arg &= (1 << 64) - 1
    if conv == "%":
        return "%"
    if conv == "d":
        v = arg - (1 << 64) if arg >> 63 else arg
        text = str(v)
    elif conv == "u":
        text = str(arg)
    elif conv == "x":
        text = f"{arg:x}"
    elif conv == "p":
        return f"0x{arg:016x}"
    elif conv == "c":
        text = chr(arg & 0xFF)
    else:                                     # s: arg is (address, the string) or None
        text = "(null)" if arg is None else arg[1]
    if len(text) >= width:
        return text
    if left:
        return text + " " * (width - len(text))
    if zero and conv in "dux":
        if text.startswith("-"):
            return "-" + "0" * (width - len(text)) + text[1:]
        return "0" * (width - len(text)) + text
    return " " * (width - len(text)) + text


SPEC = re.compile(r"%-?0?\d*[duxpsc%]")


def render(fmt, args):
    out, k = "", 0
    pos = 0
    for m in SPEC.finditer(fmt):
        out += fmt[pos:m.start()]
        if m.group() == "%%":
            out += "%"
        else:
            out += fmt_one(m.group(), args[k])
            k += 1
        pos = m.end()
    return out + fmt[pos:]


def hexdump(addr, data):
    lines = []
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        hexes = [f"{b:02x}" for b in chunk] + ["  "] * (16 - len(chunk))
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{addr + off:016x}  {' '.join(hexes[:8])}  {' '.join(hexes[8:])}  |{text}|")
    return "".join(l + "\r\n" for l in lines)


def asm_string(s):
    parts, run = [], ""
    for ch in s:
        if 32 <= ord(ch) < 127 and ch != '"':
            run += ch
        else:
            if run:
                parts.append(f'"{run}"')
                run = ""
            parts.append(str(ord(ch)))
    if run:
        parts.append(f'"{run}"')
    return ", ".join(parts + ["0"])


REGS = ["rsi", "rdx", "rcx", "r8", "r9"]


def program(calls, dump):
    """calls: [(fmt, [args])] (an `s` arg is a string, or None); dump: bytes for hexdump."""
    code, data = [], []
    for n, (fmt, args) in enumerate(calls):
        data.append(f"fmt{n}: db {asm_string(fmt)}")
        values = []
        k = 0
        for m in SPEC.finditer(fmt):
            if m.group() == "%%":
                continue
            a = args[k]
            if m.group()[-1] == "s":
                if a is None:
                    values.append("0")
                else:
                    data.append(f"str{n}_{k}: db {asm_string(a[1])}")
                    values.append(f"str{n}_{k}")
            else:
                values.append(str(a))
            k += 1
        stack = values[5:]
        pad = len(stack) % 2                    # rsp 16-aligned at the call
        if pad:
            code.append("    sub rsp, 8")
        for v in reversed(stack):
            code.append(f"    mov rax, {v}\n    push rax")
        for reg, v in zip(REGS, values):
            code.append(f"    mov {reg}, {v}")
        code.append(f"    lea rdi, [rel fmt{n}]\n    call [rel printk]")
        code.append(f"    mov [rel counts + {n * 8}], rax")
        if stack or pad:
            code.append(f"    add rsp, {8 * (len(stack) + pad)}")
    data.append('dump_marker: db "<dump>"')
    data.append("dump: db " + ", ".join(str(b) for b in dump))
    code.append(f"    lea rdi, [rel dump]\n    mov esi, {len(dump)}\n    call [rel hexdump]")
    # report the counts printk returned
    code.append(f"    mov ecx, {len(calls)}\n    lea rbx, [rel counts]")
    return code, data


MODULE = r"""
bits 64
org 0x80000
start:                              ; rdi = printk, rsi = hexdump
    push rbx
    push rbp
    mov rbp, rsp
    and rsp, -16
    mov [rel printk], rdi
    mov [rel hexdump], rsi
CODE
    ; the counts printk returned, one per call: "counts: 5 7 ..."
    lea rdi, [rel s_counts]
    call [rel printk]
.count:
    push rcx
    push rbx
    lea rdi, [rel s_one]
    mov rsi, [rbx]
    sub rsp, 8
    call [rel printk]
    add rsp, 8
    pop rbx
    pop rcx
    add rbx, 8
    loop .count
    lea rdi, [rel s_nl]
    call [rel printk]
    mov rsp, rbp
    pop rbp
    pop rbx
    ret
s_counts: db "counts:", 0
s_one:    db " %u", 0
s_nl:     db 13, 10, 0
DATA
align 8
printk:  dq 0
hexdump: dq 0
counts:  times 64 dq 0
"""


def build(calls, dump):
    code, data = program(calls, dump)
    return MODULE.replace("CODE", "\n".join(code)).replace("DATA", "\n".join(data))


def expected(calls, dump, dump_addr):
    out = "".join(render(f, a) for f, a in calls)
    out += hexdump(dump_addr, dump)
    out += "counts:" + "".join(f" {len(render(f, a))}" for f, a in calls) + "\r\n"
    return out + "done\r\n"


@functools.lru_cache(maxsize=None)
def module_and_want(key):
    from ring.qemu import assemble_flat
    calls, dump = CASES[key] if isinstance(key, str) else random_case(key)
    src = build(calls, dump)
    code = assemble_flat(src)
    dump_addr = MOD + code.index(b"<dump>") + len(b"<dump>")
    return code, expected(calls, dump, dump_addr)


def s(text):
    return (None, text)


CASES = {
    "the basics": ([("hello, %s!\r\n", [s("world")]),
                    ("%d %u %x %c%%\r\n", [-42, 42, 0xbeef, ord("A")]),
                    ("%p\r\n", [0xffffffff80100000])],
                   b"Hello, world!\n\x00\x01\x02\xff the kernel log\x7f"),
    "widths": ([("[%5d] [%-6s] [%08x] [%3s]\r\n", [42, s("ab"), 0x1f, s("toolong")]),
                ("[%05d] [%2u] [%s]\r\n", [-7, 12345, None])],
               bytes(range(0, 40))),
    "many arguments": ([("%d %d %d %d %d %d %d %d\r\n", [1, 2, 3, 4, 5, 6, 7, 8]),
                        ("%s=%x %s=%x %s=%x\r\n", [s("rax"), 1, s("rbx"), 2, s("rcx"), 3])],
                       b"\x00" * 16),
}


def random_case(seed):
    import random
    rng = random.Random(seed)
    calls = []
    for _ in range(rng.randint(3, 6)):
        parts, args = [], []
        for _ in range(rng.randint(1, 7)):
            conv = rng.choice("duxpsc")
            flags = ""
            if conv in "dux" and rng.random() < 0.4:
                flags = rng.choice(["0", ""]) + str(rng.randint(1, 12))
            if conv == "s" and rng.random() < 0.4:
                flags = rng.choice(["-", ""]) + str(rng.randint(1, 10))
            parts.append(f"%{flags}{conv}")
            if conv == "d":
                args.append(rng.randrange(-10**12, 10**12) & ((1 << 64) - 1))
            elif conv in "ux":
                args.append(rng.getrandbits(rng.choice([8, 32, 64])))
            elif conv == "p":
                args.append(rng.getrandbits(64))
            elif conv == "c":
                args.append(rng.randrange(33, 127))
            else:
                args.append(None if rng.random() < 0.1 else
                            s("".join(rng.choice("abcdefghij ") for _ in range(rng.randint(0, 9)))))
        sep = rng.choice([" ", ", ", " | "])
        calls.append((sep.join(parts) + "\r\n", args))
    dump = rng.randbytes(rng.randint(1, 70))
    return calls, dump


def case(name, key, hidden=False):
    code, want = module_and_want(key)
    return {"name": name, "hidden": hidden, "inject": {"modules": [code.hex()]},
            "expect": {"serial": want, "timeout": 20}}


def fixed_tests(ctx):
    return [case(n, n) for n in CASES]


def generate(rng, count, ctx):
    return [case(f"random {i}", rng.randrange(1 << 30), True) for i in range(count)]
