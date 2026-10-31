"""Level 19: a program computes, writes, and keeps its own data at its gs base, while the
APIC timer interrupts every `period` ticks. Some timer interrupts arrive during a
system call; the original kernel's handler then swaps to the wrong gs."""

import functools

PROGRAM = r"""
bits 64
org 0x400000
    mov eax, 158                    ; arch_prctl(ARCH_SET_GS, mine)
    mov edi, 0x1001
    lea rsi, [rel mine]
    syscall
    mov r12d, 1                     ; the round
.round:
    mov ecx, 2000                   ; some computing
    xor eax, eax
.work:
    add rax, rcx
    rol rax, 3
    loop .work
    mov al, r12b                    ; "round N\n"
    add al, '0'
    cmp r12d, 10
    jb .one
    mov byte [rel line + 6], '1'
    mov al, r12b
    add al, '0' - 10
    mov [rel line + 7], al
    mov edx, 9
    jmp .say
.one:
    mov [rel line + 6], al
    mov byte [rel line + 7], 10
    mov edx, 8
.say:
    mov eax, 1
    mov edi, 1
    lea rsi, [rel line]
    syscall
    inc r12d
    cmp r12d, 16
    jbe .round
    mov rax, [gs:16]                ; my data, through my gs base: still as I left it?
    cmp rax, [rel expected]
    jne .changed
    mov eax, 1
    mov edi, 1
    lea rsi, [rel ok]
    mov edx, ok_len
    syscall
    mov eax, 60
    xor edi, edi
    syscall
.changed:
    mov eax, 1
    mov edi, 1
    lea rsi, [rel bad]
    mov edx, bad_len
    syscall
    mov eax, 60
    mov edi, 1
    syscall
line: db "round ??", 10
ok:   db "my data is intact", 10
ok_len equ $ - ok
bad:  db "my data changed!", 10
bad_len equ $ - bad
align 8
mine:     dq 0x1111111111111111, 0x2222222222222222, 0x3333333333333333, 0x4444444444444444
expected: dq 0x3333333333333333
"""

WANT = "".join(f"round {r}\n" for r in range(1, 17)) + "my data is intact\n" + \
    "user program exited with status 0\r\n"

PERIODS = [20011, 5000, 50000, 3000, 7919, 12000, 31337]


@functools.lru_cache(maxsize=None)
def program() -> bytes:
    from ring.qemu import assemble_flat
    return assemble_flat(PROGRAM)


def case(name, period, hidden=False):
    return {"name": name, "hidden": hidden,
            "inject": {"modules": [program().hex()], "cmdline": f"period={period}"},
            "expect": {"serial": WANT, "check": True, "timeout": 15}}


def check(test, run, regs, screen, serial):
    """The timer must really be running (no fair turning it off)."""
    if "percpu" not in run.symbols:
        return []
    ticks = int.from_bytes(run.read(run.symbols["percpu"] + 16, 8), "little")
    if ticks < 3:
        return [f"the timer ticked {ticks} times: it must keep interrupting (every `period` "
                "APIC timer counts), through the program and its system calls"]
    return []


def fixed_tests(ctx):
    return [case(f"period {p}", p) for p in PERIODS[:3]]


def generate(rng, count, ctx):
    return [case(f"period {p}", p, True) for p in PERIODS[3:]] + \
        [case(f"period {p}", p, True) for p in sorted(rng.sample(range(2000, 60000), count))]


def witness_test(w, ctx):
    if set(w) != {"period"} or not isinstance(w["period"], int) or not 1000 <= w["period"] <= 100000:
        raise ValueError("the witness is a timer period from 1000 to 100000: `;! witness period = 5000`")
    return case("witness", w["period"])
