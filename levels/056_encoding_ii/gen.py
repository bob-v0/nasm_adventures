"""Level 56: the instructions to encode by hand (REX, prefixes, SSE, VEX). The player's bytes must decode to the
same instructions (any valid encoding), and run to the same registers."""

TARGET = """\
mov rax, 0x1122334455667788
mov r9, rax
lea r10, [r9+8]
sub r10, rax
push r9
pop r11
mov r12d, 0x7F
mov [rsp-16], r12
movzx r13d, byte [rsp-16]
inc r13
mov ax, 0x1234
movsx rdx, word [rsp-16]
lock xadd [rsp-16], r12d
mov r14, [rsp-16]
mov dil, 7
pcmpeqd xmm0, xmm0
movdqu [rsp-32], xmm0
pxor xmm8, xmm8
psubd xmm8, xmm0
cvtsi2sd xmm1, r12
addsd xmm1, xmm1
cvttsd2si r8, xmm1
vpaddd ymm2, ymm0, ymm0
vpaddd ymm9, ymm2, ymm8
vmovd esi, xmm9
vzeroupper
"""

REGS = None   # filled in below, from running the target


def _expected():
    global REGS
    if REGS is None:
        import tempfile
        from pathlib import Path
        from ring.build import build
        from ring.emu import Machine
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "t.asm").write_text(TARGET)
            m = Machine(build(Path(d) / "t.asm", Path(d) / "b", "fragment"))
            m.run(1000)
            REGS = {r: m.reg(r) for r in ("rax", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11", "r12",
                                         "r13", "r14")}
    return REGS


def fixed_tests(ctx):
    return [{"name": "the instructions run", "expect": {"regs": _expected()}}]


def audit(build):
    from ring.checks import disassemble
    from ring.machine_code import assemble, compare, listing
    import re
    problems = []
    for n, line in enumerate(build.source.read_text().splitlines(), 1):
        code = line.split(";")[0].strip()
        if code and not re.fullmatch(r"(\.?\w+:\s*)?(db\s+.*)?", code, re.I):
            problems.append(f"line {n}: only `db` lines (and labels) here: `{code}`")
            break
    start, end = build.code_range
    from ring.emu import Machine
    got = listing(Machine(build).read(start, end - start), start)
    diff = compare(listing(assemble(TARGET)), got)
    return [("written with db only", not problems, problems[0] if problems else ""),
            ("the bytes decode to the 26 instructions", not diff, diff[0] if diff else "")]
