"""Level 57: the instructions to encode by hand. The player's bytes must decode to the
same instructions (any valid encoding), and run to the same registers."""

TARGET = """\
mov eax, 1
mov ecx, 0x12345678
add eax, ecx
sub eax, 5
xor edx, edx
mov ebx, eax
inc ecx
shl eax, 4
mov [rsp-8], eax
mov esi, [rsp-8]
lea edi, [rax+rcx*2+16]
imul eax, ecx, 3
cmp eax, ebx
and al, 0x0F
mov byte [rsp-1], 0x41
movzx edx, byte [rsp-1]
neg ebx
test eax, eax
sete cl
mov edx, 5
again:
add eax, edx
dec edx
jnz again
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
            REGS = {r: m.reg(r) for r in ("rax", "rbx", "rcx", "rdx", "rsi", "rdi")}
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
            ("the bytes decode to the 23 instructions", not diff, diff[0] if diff else "")]
