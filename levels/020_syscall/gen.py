"""Level 20: user programs (at 0x400000, ring 3) call the kernel with `syscall`, Linux's
way: rax = the number, arguments in rdi, rsi, rdx; the result in rax; every register but
rcx and r11 kept."""

import functools

HEAD = r"""
bits 64
org 0x400000
%macro say 1+                       ; write(1, text, length)
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
    "hello": (r"""
    say "hello, world", 10
    exit 0
""", "hello, world\n", 0),

    "two writes": (r"""
    say "first ", "line", 10
    say "second line", 10
    exit 7
""", "first line\nsecond line\n", 7),

    # write returns the count; every register but rax, rcx and r11 comes back as it was
    "registers kept": (r"""
    mov rbx, 0x1111111111111111
    mov rbp, 0x2222222222222222
    mov r8, 0x3333333333333333
    mov r9, 0x4444444444444444
    mov r10, 0x5555555555555555
    mov r12, 0x6666666666666666
    mov r13, 0x7777777777777777
    mov r14, 0x8888888888888888
    mov r15, 0x9999999999999999
    mov r11, rsp                    ; (rsp, to compare after)
    mov [rel saved_rsp], r11
    mov eax, 1
    mov edi, 1
    lea rsi, [rel text]
    mov edx, 6
    syscall
    cmp rax, 6
    jne .count
    cmp rdi, 1
    jne .changed
    lea rcx, [rel text]
    cmp rsi, rcx
    jne .changed
    cmp rdx, 6
    jne .changed
    mov rcx, 0x1111111111111111
    cmp rbx, rcx
    jne .changed
    mov rcx, 0x2222222222222222
    cmp rbp, rcx
    jne .changed
    mov rcx, 0x3333333333333333
    cmp r8, rcx
    jne .changed
    mov rcx, 0x4444444444444444
    cmp r9, rcx
    jne .changed
    mov rcx, 0x5555555555555555
    cmp r10, rcx
    jne .changed
    mov rcx, 0x6666666666666666
    cmp r12, rcx
    jne .changed
    mov rcx, 0x7777777777777777
    cmp r13, rcx
    jne .changed
    mov rcx, 0x8888888888888888
    cmp r14, rcx
    jne .changed
    mov rcx, 0x9999999999999999
    cmp r15, rcx
    jne .changed
    cmp rsp, [rel saved_rsp]
    jne .stack
    say "all kept", 10
    exit 0
.count:
    say "write didn't return 6", 10
    exit 1
.changed:
    say "a register changed", 10
    exit 1
.stack:
    say "rsp changed", 10
    exit 1
text: db "6 byte"
align 8
saved_rsp: dq 0
""", "6 byteall kept\n", 0),

    # a program that left the direction flag set: the kernel's string instructions must
    # still go forwards (SFMASK clears DF on the way in)
    "direction flag": (r"""
    std
    say "forwards", 10
    cld
    exit 0
""", "forwards\n", 0),

    # the kernel must not print its own memory for a program
    "bad pointer": (r"""
    mov eax, 1
    mov edi, 1
    mov rsi, 0xFFFFFFFF80100000
    mov edx, 16
    syscall
    cmp rax, -14
    jne .no
    say "EFAULT", 10
    exit 0
.no:
    say "no EFAULT", 10
    exit 1
""", "EFAULT\n", 0),

    "unknown call": (r"""
    mov eax, 999
    syscall
    cmp rax, -38
    jne .no
    say "ENOSYS", 10
    exit 0
.no:
    say "no ENOSYS", 10
    exit 1
""", "ENOSYS\n", 0),

    # arch_prctl(ARCH_SET_GS, address): the program's own gs base, kept across calls
    "gs base": (r"""
    mov eax, 158
    mov edi, 0x1001
    lea rsi, [rel mine]
    syscall
    test rax, rax
    jnz .failed
    say "set", 10
    mov rax, [gs:0]
    mov rcx, 0x0123456789ABCDEF
    cmp rax, rcx
    jne .lost
    say "kept", 10
    exit 0
.failed:
    say "arch_prctl failed", 10
    exit 1
.lost:
    say "gs:0 isn't mine", 10
    exit 1
align 8
mine: dq 0x0123456789ABCDEF
""", "set\nkept\n", 0),
}


@functools.lru_cache(maxsize=None)
def program(name: str) -> bytes:
    from ring.qemu import assemble_flat
    return assemble_flat(HEAD + PROGRAMS[name][0])


def case(name, hidden=False):
    _, out, status = PROGRAMS[name]
    return {"name": name, "hidden": hidden, "inject": {"modules": [program(name).hex()]},
            "expect": {"serial": out + f"user program exited with status {status}\r\n",
                       "timeout": 10}}


def fixed_tests(ctx):
    return [case("hello"), case("registers kept"), case("bad pointer")]


def generate(rng, count, ctx):
    return [case(n, True) for n in ("two writes", "direction flag", "unknown call", "gs base")]
