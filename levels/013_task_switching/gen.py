"""Level 13: several programs (ELF files), taking turns: sched_yield (24) gives the CPU to
the next one. Each must find its registers, stack and memory as it left them."""

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
%macro yield 0
    mov eax, 24
    syscall
%endmacro
%macro exit 1
    mov eax, 60
    mov edi, %1
    syscall
%endmacro
section .text
"""

# a task that says its name N times, yielding after each
def talker(name, times, status):
    body = "\n".join(f'    say "{name}{k}", 10\n    yield' for k in range(1, times + 1))
    return COMMON + f"_start:\n{body}\n    exit {status}\n"


# a task that fills every register it may keep with its own pattern, yields, and checks
def keeper(tag, rounds):
    regs = ["rbx", "rbp", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r12", "r13", "r14", "r15"]
    fill = "\n".join(f"    mov {r}, 0x{tag:02x}{i:02x}{tag:02x}{i:02x}{tag:02x}{i:02x}{tag:02x}{i:02x}"
                     for i, r in enumerate(regs))
    check = "\n".join(f"    mov rax, 0x{tag:02x}{i:02x}{tag:02x}{i:02x}{tag:02x}{i:02x}{tag:02x}{i:02x}\n"
                      f"    cmp {r}, rax\n    jne bad" for i, r in enumerate(regs))
    return COMMON + f"""_start:
    mov [saved_rsp], rsp
    push 0x{tag:02x}                       ; something of its own on its stack
    mov ecx, {rounds}
.round:
    push rcx
{fill}
    yield
{check}
    pop rcx
    dec rcx
    jnz .round
    pop rax
    cmp rax, 0x{tag:02x}
    jne bad
    cmp rsp, [saved_rsp]
    jne bad
    say "task {tag:x}: registers kept", 10
    exit 0
bad:
    say "task {tag:x}: a register changed", 10
    exit 1
section .bss
saved_rsp: resq 1
"""


def faulter():
    return COMMON + """_start:
    say "F1", 10
    yield
    mov rax, [0]                    ; a null pointer: killed
    say "F2", 10
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


def run(programs):
    """Round robin, as the kernel must do it: the expected output."""
    out, alive = [], list(range(len(programs)))
    steps = [p["steps"] for p in programs]
    pos = [0] * len(programs)
    while alive:
        for t in list(alive):
            if t not in alive:
                continue
            kind, text = steps[t][pos[t]]
            out.append(text)
            pos[t] += 1
            if kind == "end":
                alive.remove(t)
    return "".join(out) + "all tasks done\r\n"


def talker_spec(name, times, status):
    steps = [("yield", f"{name}{k}\n") for k in range(1, times + 1)]
    steps.append(("end", f"process exited with status {status}\r\n"))
    return {"src": talker(name, times, status), "steps": steps}


def keeper_spec(tag, rounds):
    steps = [("yield", "")] * rounds
    steps.append(("end", f"task {tag:x}: registers kept\nprocess exited with status 0\r\n"))
    return {"src": keeper(tag, rounds), "steps": steps}


def faulter_spec():
    import io
    from elftools.elf.elffile import ELFFile
    text = ELFFile(io.BytesIO(elf(faulter()))).get_section_by_name(".text")
    at = text["sh_addr"] + text.data().index(bytes.fromhex("488b042500000000"))
    return {"src": faulter(), "steps": [
        ("yield", "F1\n"),
        ("end", f"#PF at 0x{at:016x}, error code 0x0000000000000004, cr2 0x0000000000000000\r\n"
                "process killed\r\n")]}


def case(name, specs, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"modules": [elf(s["src"]).hex() for s in specs]},
            "expect": {"serial": run(specs), "timeout": 30}}


def fixed_tests(ctx):
    return [case("two tasks", [talker_spec("A", 3, 0), talker_spec("B", 3, 0)]),
            case("registers kept", [keeper_spec(0xA, 5), keeper_spec(0xB, 5), talker_spec("C", 4, 7)])]


def generate(rng, count, ctx):
    out = [case("uneven", [talker_spec("A", 1, 1), talker_spec("B", 5, 2), talker_spec("C", 3, 3)], True),
           case("a fault kills one", [faulter_spec(), talker_spec("A", 3, 0)], True)]
    for i in range(count):
        specs = [keeper_spec(t, rng.randint(1, 6)) if rng.random() < 0.5 else
                 talker_spec("ABCDEFGH"[t], rng.randint(1, 5), rng.randrange(256))
                 for t in range(rng.randint(2, 5))]
        out.append(case(f"random {i}", specs, True))
    return out
