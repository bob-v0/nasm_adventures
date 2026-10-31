"""Level 55: the instruction subset, its random generator, and lengths checked by
Capstone."""

M, I8, IZ, I16, PFX, MOVI, GRP3 = 1, 2, 4, 8, 16, 32, 64

PREFIXES = [0x66, 0x67, 0xF0, 0xF2, 0xF3, 0x2E, 0x3E, 0x26, 0x64, 0x65, 0x36]


def _one():
    t = {}
    for base in range(0x00, 0x40, 8):          # add, or, adc, sbb, and, sub, xor, cmp
        for k in range(4):
            t[base + k] = M
        t[base + 4] = I8
        t[base + 5] = IZ
    for op in range(0x50, 0x60):
        t[op] = 0                               # push/pop r64
    t.update({0x63: M, 0x68: IZ, 0x69: M | IZ, 0x6A: I8, 0x6B: M | I8})
    for op in range(0x70, 0x80):
        t[op] = I8                              # jcc rel8
    t.update({0x80: M | I8, 0x81: M | IZ, 0x83: M | I8})
    for op in range(0x84, 0x8C):
        t[op] = M                               # test, xchg, mov
    t.update({0x8D: M, 0x8F: M})
    for op in range(0x90, 0x9A):
        t[op] = 0                               # xchg/nop, cwde, cdq
    t.update({0xA8: I8, 0xA9: IZ})
    for op in range(0xB0, 0xB8):
        t[op] = I8                              # mov r8, imm8
    for op in range(0xB8, 0xC0):
        t[op] = MOVI                            # mov r, imm (16/32/64)
    t.update({0xC0: M | I8, 0xC1: M | I8, 0xC2: I16, 0xC3: 0, 0xC6: M | I8, 0xC7: M | IZ,
              0xC9: 0, 0xCC: 0, 0xD0: M, 0xD1: M, 0xD2: M, 0xD3: M, 0xE8: IZ, 0xE9: IZ,
              0xEB: I8, 0xF6: M | GRP3, 0xF7: M | GRP3, 0xFE: M, 0xFF: M})
    for p in PREFIXES:
        t[p] = PFX
    return t


def _two():
    t = {0x05: 0, 0x0B: 0, 0xA2: 0, 0x1F: M, 0xAF: M, 0xB6: M, 0xB7: M, 0xBE: M, 0xBF: M,
         0xC1: M, 0xC2: M | I8, 0xC6: M | I8, 0x38: M, 0x3A: M | I8}  # 38/3A: a 3rd opcode byte
    for op in list(range(0x10, 0x18)) + list(range(0x28, 0x30)) + list(range(0x40, 0x50)) \
            + list(range(0x51, 0x70)) + list(range(0x74, 0x77)) + [0x7E, 0x7F] \
            + list(range(0x90, 0xA0)) + list(range(0xD1, 0x100)):
        t[op] = M
    for op in range(0x70, 0x74):
        t[op] = M | I8                          # pshufd, shifts by imm8
    for op in range(0x80, 0x90):
        t[op] = IZ                              # jcc rel32
    t.pop(0xFF, None)
    return t


ONE, TWO = _one(), _two()


def encode(rng):
    """A random instruction from the subset: (bytes, expected length)."""
    out = bytearray()
    opsize = rex_w = False
    for _ in range(rng.choice([0, 0, 0, 1, 1, 2, 3])):
        p = rng.choice(PREFIXES)
        opsize |= p == 0x66
        out.append(p)
    if rng.random() < 0.5:
        rex = 0x40 | rng.randrange(16)
        rex_w = bool(rex & 8)
        out.append(rex)
    if rng.random() < 0.7:
        op = rng.choice([o for o, f in ONE.items() if not f & PFX])
        flags = ONE[op]
        out.append(op)
        if op in (0xE8, 0xE9) and opsize:           # (66 with near branches: avoid)
            return encode(rng)
    else:
        op = rng.choice(list(TWO))
        flags = TWO[op]
        out += bytes([0x0F, op])
        if op in (0x38, 0x3A):
            out.append(rng.choice([0x00, 0x04, 0x0B, 0x1C] if op == 0x38 else [0x0F, 0x16, 0x20, 0x22]))
        if 0x80 <= op <= 0x8F and opsize:
            return encode(rng)
    if flags & M:
        mod, reg, rm = rng.randrange(4), rng.randrange(8), rng.randrange(8)
        if flags & GRP3 and rng.random() < 0.5:
            reg = rng.randrange(2)                  # test: has an immediate
        out.append(mod << 6 | reg << 3 | rm)
        if mod != 3 and rm == 4:
            base = rng.randrange(8)
            out.append(rng.randrange(256) & 0xF8 | base)
            if mod == 0 and base == 5:
                out += rng.randbytes(4)
        if mod == 0 and rm == 5:
            out += rng.randbytes(4)
        elif mod == 1:
            out += rng.randbytes(1)
        elif mod == 2:
            out += rng.randbytes(4)
        if flags & GRP3 and reg < 2:
            out += rng.randbytes(1 if op == 0xF6 else 2 if opsize and not rex_w else 4)
    if flags & I8:
        out += rng.randbytes(1)
    if flags & IZ:
        out += rng.randbytes(2 if opsize and not rex_w and op not in (0xE8, 0xE9) else 4)
    if flags & I16:
        out += rng.randbytes(2)
    if flags & MOVI:
        out += rng.randbytes(8 if rex_w else 2 if opsize else 4)
    return bytes(out)


def _valid(code: bytes) -> bool:
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs
    ins = next(Cs(CS_ARCH_X86, CS_MODE_64).disasm(code + b"\x90" * 15, 0), None)
    return ins is not None and ins.size == len(code)


def sample(rng):
    while True:
        code = encode(rng)
        if len(code) <= 15 and _valid(code):
            return code


def case(name, code, rng, hidden=False):
    junk = rng.randbytes(16)                    # what follows: the next instruction
    return {"name": name, "hidden": hidden, "regs": {"rdi": "@code"},
            "mem": [{"sym": "code", "hex": (code + junk).hex()}],
            "expect": {"regs": {"rax": len(code)}, "bytes": code.hex(" ")}}


FIXED = [("ret", "c3"), ("push rbp", "55"), ("mov rbp, rsp", "48 89 e5"),
         ("add eax, 1 (83 /0 ib)", "83 c0 01"), ("mov eax, 1", "b8 01 00 00 00"),
         ("mov ax, 1", "66 b8 01 00"), ("mov rax, imm64", "48 b8 88 77 66 55 44 33 22 11"),
         ("mov [rsp-8], eax", "89 44 24 f8"), ("lea rax, [rip+0x100]", "48 8d 05 00 01 00 00"),
         ("call rel32", "e8 00 00 00 00"), ("test byte [rax], 1", "f6 00 01"),
         ("not dword [rax]", "f7 10"), ("movdqu xmm0, [rsi]", "f3 0f 6f 06"),
         ("jne rel32", "0f 85 10 00 00 00"), ("pshufd xmm0, xmm1, 0x1b", "66 0f 70 c1 1b"),
         ("lock add [rbx+rcx*8+0x100], eax", "f0 01 84 cb 00 01 00 00")]


def fixed_tests(ctx):
    import random
    rng = random.Random(55)
    return [case(name, bytes.fromhex(h), rng) for name, h in FIXED]


def generate(rng, count, ctx):
    out = []
    for i in range(count):
        code = sample(rng)
        out.append(case(f"random {i}: {code.hex(' ')}", code, rng, True))
    return out
