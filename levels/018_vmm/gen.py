"""Level 18: several programs, one after another, each in its own address space, all
loaded at 0x400000. They must not see each other's memory, a faulting one must not take
the others down, and memory must come back when each one ends."""

import functools

HEAD = r"""
bits 64
org 0x400000
%macro say 1+
    jmp %%over
%%text: db %1
%%over:
    mov eax, 1
    mov edi, 1
    lea rsi, [rel %%text]
    mov edx, %%over - %%text
    syscall
%endmacro
%macro exit 1
    mov eax, 60
    mov edi, %1
    syscall
%endmacro
"""

PROGRAMS = {
    "writer": (r"""
    mov rax, 0x5EC2E75EC2E75EC2     ; a secret, at an address no one gave it: a fresh page
    mov [0x10000000], rax
    say "A wrote its secret", 10
    exit 0
""", "A wrote its secret\n", 0),
    "reader": (r"""
    mov rax, [0x10000000]           ; the same address, in another address space
    test rax, rax
    jnz .leak
    cmp dword [rel me], 'BBBB'      ; and at 0x400000: my own code, not A's
    jne .wrong
    say "B sees fresh memory", 10
    exit 0
.leak:
    say "B sees A's secret!", 10
    exit 1
.wrong:
    say "B's image isn't B's", 10
    exit 1
me: db "BBBB"
""", "B sees fresh memory\n", 0),
    "snoop": (r"""
    mov rax, [0x100000]             ; the kernel's memory, mapped in every address space
    say "read the kernel!", 10
    exit 1
""", None, None),
    "big": (r"""
    mov rbx, 0x20000000             ; 4 MiB of fresh pages, written and read back
    mov ecx, 1024
.fill:
    mov [rbx], rbx
    add rbx, 4096
    loop .fill
    mov rbx, 0x20000000
    mov ecx, 1024
.check:
    cmp [rbx], rbx
    jne .bad
    add rbx, 4096
    loop .check
    say "4 MiB ok", 10
    exit 0
.bad:
    say "4 MiB wrong", 10
    exit 1
""", "4 MiB ok\n", 0),
    "deep stack": (r"""
    mov ecx, 400                    ; 400 frames of 256 bytes: 100 KiB of stack, on demand
    call down
    say "deep stack ok", 10
    exit 0
down:
    sub rsp, 248
    mov [rsp], rcx
    dec ecx
    jz .up
    call down
.up:
    add rsp, 248
    ret
""", "deep stack ok\n", 0),
}


@functools.lru_cache(maxsize=None)
def program(name: str) -> bytes:
    from ring.qemu import assemble_flat
    return assemble_flat(HEAD + PROGRAMS[name][0])


def run_of(names):
    out = ""
    for n in names:
        _, said, status = PROGRAMS[n]
        if said is None:          # snoop: killed
            code = program(n)
            at = 0x400000                     # its first instruction
            out += (f"#PF at 0x{at:016x}, error code 0x0000000000000005, cr2 0x0000000000100000\r\n"
                    "process killed\r\n")
        else:
            out += said + f"process exited with status {status}\r\n"
    return out + "all processes done\r\n"


def case(name, names, memory=None, hidden=False):
    inj = {"modules": [program(n).hex() for n in names]}
    if memory:
        inj["memory"] = memory
    return {"name": name, "hidden": hidden, "inject": inj,
            "expect": {"serial": run_of(names), "timeout": 60}}


def fixed_tests(ctx):
    return [case("isolation", ["writer", "reader"]),
            case("a fault kills one, not all", ["snoop", "reader"])]


def generate(rng, count, ctx):
    return [case("24 processes of 4 MiB in 48 MiB", ["big"] * 24, memory="48M", hidden=True),
            case("a deep stack", ["deep stack", "writer", "deep stack"], hidden=True),
            case("mixed", ["writer", "snoop", "big", "reader", "deep stack"], hidden=True)]
