"""Level 11: blocking (nanosleep), idling, and priorities (setpriority)."""

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
%macro sleep_ms 1
    mov qword [ts], %1 / 1000
    mov qword [ts + 8], (%1 % 1000) * 1000000
    mov eax, 35
    mov rdi, ts
    xor esi, esi
    syscall
%endmacro
%macro nice 1
    mov eax, 141
    xor edi, edi
    xor esi, esi
    mov rdx, %1
    syscall
%endmacro
%macro yield 0
    mov eax, 24
    syscall
%endmacro
%macro exit 1
    mov eax, 60
    mov edi, %1
    syscall
%endmacro
section .bss
ts: resq 2
section .text
_start:
"""

EXIT = "process exited with status 0\r\n"


def sleeper(name, ms):
    return COMMON + f'    say "{name}: sleeping", 10\n    sleep_ms {ms}\n    say "{name}: awake", 10\n    exit 0\n'


def niced(name, nice, times):
    body = "\n".join(f'    say "{name}{k}", 10\n    yield' for k in range(1, times + 1))
    return COMMON + f"    nice {nice}\n    yield\n{body}\n    exit 0\n"


def busy(name, iterations):
    return COMMON + f"""    say "{name}: started", 10
    mov rcx, {iterations}
.spin:
    dec rcx
    jnz .spin
    say "{name}: done", 10
    exit 0
"""


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


def case(name, sources, want=None, before=None, hidden=False):
    """want: the exact output; or before: [(a, b)]: line a comes before line b."""
    exp = {"timeout": 60}
    if want is not None:
        exp["serial"] = want
    else:
        exp["check"] = True
        exp["before"] = before
        exp["exits"] = len(sources)
    return {"name": name, "hidden": hidden, "inject": {"modules": [elf(s).hex() for s in sources]},
            "expect": exp}


def check(test, run, regs, screen, serial):
    lines = [l for l in serial.decode("latin-1").replace("\r\n", "\n").split("\n") if l]
    problems = []
    if not lines or lines[-1] != "all tasks done":
        return [f"the output should end with `all tasks done`: {lines[-3:]}"]
    exits = sum(l.startswith("process exited") for l in lines)
    if exits != test.expect["exits"]:
        problems.append(f"{test.expect['exits']} tasks, {exits} exits")
    for a, b in test.expect["before"]:
        if a not in lines or b not in lines:
            problems.append(f"expected both `{a}` and `{b}`; output: {lines}")
        elif lines.index(a) > lines.index(b):
            problems.append(f"`{a}` should come before `{b}`; output: {lines}")
    return problems


def sleepers(order):
    """order: [(name, ms)]: they all say they're sleeping (in turn), then wake by time."""
    want = "".join(f"{n}: sleeping\n" for n, _ in order)
    for n, _ in sorted(order, key=lambda x: x[1]):
        want += f"{n}: awake\n" + EXIT
    return case("sleepers: " + ", ".join(f"{n} {ms} ms" for n, ms in order),
                [sleeper(n, ms) for n, ms in order], want=want + "all tasks done\r\n")


def fixed_tests(ctx):
    pri = "".join(f"H{k}\n" for k in (1, 2, 3)) + EXIT + "".join(f"L{k}\n" for k in (1, 2, 3)) + EXIT
    return [sleepers([("A", 300), ("B", 100), ("C", 200)]),
            case("priorities", [niced("L", 5, 3), niced("H", -5, 3)], want=pri + "all tasks done\r\n")]


def generate(rng, count, ctx):
    out = [case("a busy task doesn't keep a sleeper asleep",
                [busy("S", 40_000_000), sleeper("A", 20)],
                before=[("A: awake", "S: done")], hidden=True)]
    for i in range(count):
        names = "ABCDE"[:rng.randint(2, 5)]
        times = rng.sample(range(10, 400, 10), len(names))
        t = sleepers(list(zip(names, times)))
        t["hidden"] = True
        t["name"] = f"random {i}: " + t["name"]
        out.append(t)
    return out
