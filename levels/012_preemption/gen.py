"""Level 12: tasks that never yield. The APIC timer takes the CPU from them; each must
find every register, and its flags, as it was. Output order depends on timing, so each
task's own lines are checked in order, and the long task must finish last."""

import functools

COMMON = r"""
global _start
%macro say 1+
    jmp %%over
%%text: db %1
%%over:
    mov eax, 1
    mov edi, 1
    mov rsi, %%text
    mov edx, %%over - %%text
    syscall
%endmacro
%macro exit 1
    mov eax, 60
    mov edi, %1
    syscall
%endmacro
section .text
"""


def busy(name, iterations):
    """Counts, never yields, then says it's done."""
    return COMMON + f"""_start:
    say "{name}: started", 10
    mov rcx, {iterations}
    xor eax, eax
.spin:
    add rax, rcx
    dec rcx
    jnz .spin
    mov rbx, {sum(range(1, iterations + 1)) & ((1 << 64) - 1)}
    cmp rax, rbx
    jne .wrong
    say "{name}: done", 10
    exit 0
.wrong:
    say "{name}: wrong sum", 10
    exit 1
"""


def keeper(name, tag, iterations):
    """All 15 registers and the carry flag hold patterns while the timer comes and goes."""
    regs = ["rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "r8", "r9", "r10", "r11",
            "r12", "r13", "r14", "r15"]
    vals = [(tag << 56) | (i << 48) | (tag * 0x01010101 + i) for i in range(len(regs))]
    fill = "\n".join(f"    mov {r}, 0x{v:016x}" for r, v in zip(regs, vals))
    checks = "\n".join(f"    mov rsp, 0x{v:016x}\n    cmp {r}, rsp\n    jne .bad" for r, v in zip(regs, vals))
    return COMMON + f"""_start:
    say "{name}: started", 10
    mov [saved_rsp], rsp
    mov qword [count], {iterations}
{fill}
    stc
.loop:
    jnc .flag
{checks}
    mov rsp, [saved_rsp]
    stc
    dec qword [count]               ; (dec doesn't touch the carry)
    jnz .loop
    say "{name}: registers kept", 10
    exit 0
.flag:
    mov rsp, [saved_rsp]
    say "{name}: the carry flag changed", 10
    exit 1
.bad:
    mov rsp, [saved_rsp]
    say "{name}: a register changed", 10
    exit 1
section .bss
saved_rsp: resq 1
count:     resq 1
"""


def yielder(name, times):
    body = "\n".join(f'    say "{name}: {k}", 10\n    mov eax, 24\n    syscall' for k in range(1, times + 1))
    return COMMON + f"_start:\n{body}\n    exit 0\n"


@functools.lru_cache(maxsize=None)
def elf(src: str) -> bytes:
    import subprocess
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "p.asm").write_text(src)
        subprocess.run(["nasm", "-f", "elf64", "-o", f"{d}/p.o", f"{d}/p.asm"], check=True)
        subprocess.run(["ld", "-o", f"{d}/p", f"{d}/p.o"], check=True)
        return (Path(d) / "p").read_bytes()


def case(name, tasks, last=None, period=20000, hidden=False):
    """tasks: [(source, [its lines])]; last: the name whose final line must come last."""
    return {"name": name, "hidden": hidden,
            "inject": {"modules": [elf(src).hex() for src, _ in tasks], "cmdline": f"period={period}"},
            "expect": {"check": True, "timeout": 60, "tasks": [lines for _, lines in tasks],
                       "last": last}}


def check(test, run, regs, screen, serial):
    text = serial.decode("latin-1").replace("\r\n", "\n")
    lines = [l for l in text.split("\n") if l]
    if not lines or lines[-1] != "all tasks done":
        return [f"the output should end with `all tasks done`; it ends {lines[-3:] if lines else 'with nothing'}"]
    body = lines[:-1]
    exits = [l for l in body if l.startswith("process exited with status")]
    others = [l for l in body if not l.startswith("process ")]
    problems = []
    for want in test.expect["tasks"]:
        name = want[0].split(":")[0]
        got = [l for l in others if l.split(":")[0] == name]
        if got != want:
            problems.append(f"task {name} should say {want}; it said {got}")
    if len(exits) != len(test.expect["tasks"]):
        problems.append(f"{len(test.expect['tasks'])} tasks, {len(exits)} exits: {body[-4:]}")
    last = test.expect.get("last")
    if not problems and last:
        final = [l for l in others if l.startswith(last + ":")][-1]
        if others[-1] != final:
            problems.append(f"the long task {last} should finish last: the others must get turns "
                            f"while it runs, without it ever yielding. The last lines: {others[-4:]}")
    if not problems and "preemptions" in run.symbols:
        n = int.from_bytes(run.read(run.symbols["preemptions"], 8), "little")
        if n < 3:
            problems.append(f"the timer took the CPU away {n} times: it must keep doing it")
    return problems


def fixed_tests(ctx):
    return [case("no starving", [(busy("S", 3_000_000), ["S: started", "S: done"]),
                                 (busy("A", 20_000), ["A: started", "A: done"]),
                                 (busy("B", 30_000), ["B: started", "B: done"])], last="S"),
            case("registers kept", [(keeper("K", 0x4B, 300_000), ["K: started", "K: registers kept"]),
                                    (keeper("L", 0x4C, 300_000), ["L: started", "L: registers kept"])])]


def generate(rng, count, ctx):
    out = [case("mixed", [(busy("S", 2_000_000), ["S: started", "S: done"]),
                          (yielder("Y", 4), [f"Y: {k}" for k in range(1, 5)]),
                          (keeper("K", 0x4B, 40_000), ["K: started", "K: registers kept"])],
                last="S", hidden=True)]
    for i in range(count):
        period = rng.choice([7000, 15000, 40000])
        tasks = [(keeper(n, 0x40 + k, rng.randint(50_000, 200_000)), [f"{n}: started", f"{n}: registers kept"])
                 for k, n in enumerate("PQR"[:rng.randint(2, 3)])]
        out.append(case(f"random {i}", tasks, period=period, hidden=True))
    return out
