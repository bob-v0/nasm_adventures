"""Threads in the emulated kernel: clone, futex, join, and the thread scheduler."""

import pytest

from ring.build import build
from ring.emu import Machine
from ring.kernel import Injection, Kernel

THREADS = r"""
; 4 threads each add to a shared counter many times; main joins them all.
global _start
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x200000 | 0x1000000
section .text
_start:
    xor ebx, ebx
.spawn:
    cmp ebx, 4
    je .join
    mov eax, 56                 ; clone(flags, stack, 0, &tids[i], 0)
    mov edi, CLONE
    lea rsi, [stacks + 4096]
    mov rcx, rbx
    shl rcx, 12
    add rsi, rcx                ; the top of stack i
    xor edx, edx
    lea r10, [tids + rbx*4]
    xor r8d, r8d
    syscall
    test rax, rax
    jz worker
    inc ebx
    jmp .spawn
.join:                          ; wait until each tid word is 0 (CLONE_CHILD_CLEARTID)
    xor ebx, ebx
.next:
    cmp ebx, 4
    je .done
.wait:
    mov edx, [tids + rbx*4]
    test edx, edx
    jz .joined
    mov eax, 202                ; futex(&tids[i], FUTEX_WAIT, value, 0)
    lea rdi, [tids + rbx*4]
    xor esi, esi
    xor r10d, r10d
    syscall
    jmp .wait
.joined:
    inc ebx
    jmp .next
.done:
    mov eax, 231
    mov edi, [counter]
    syscall
worker:
    mov ecx, {n}
.add:
    {inc}
    dec ecx
    jnz .add
    mov eax, 60                 ; exit this thread
    xor edi, edi
    syscall
section .bss
alignb 16
stacks: resb 4 * 4096
tids: resd 4
counter: resq 1
"""


def run(tmp_path, src, inject=None, steps=2_000_000):
    (tmp_path / "s.asm").write_text(src)
    b = build(tmp_path / "s.asm", tmp_path / "b", "program")
    m = Machine(b, kernel=Kernel(inject=Injection.from_dict(inject or {}, "t")))
    m.run(steps)
    return m


def test_threads_and_join(tmp_path):
    m = run(tmp_path, THREADS.replace("{inc}", "lock inc qword [counter]").replace("{n}", "50"))
    assert (m.state, m.exit_code) == ("exited", 200), m.fault


@pytest.mark.parametrize("schedule", range(1, 6))
def test_atomic_increments_never_lose_updates(tmp_path, schedule):
    m = run(tmp_path, THREADS.replace("{inc}", "lock inc qword [counter]").replace("{n}", "50"),
            {"schedule": schedule, "quantum": 30})
    assert (m.state, m.exit_code) == ("exited", 200), m.fault


def test_a_racy_increment_loses_updates_under_some_schedule(tmp_path):
    racy = THREADS.replace("{inc}", "mov rax, [counter]\n    inc rax\n    mov [counter], rax") \
                  .replace("{n}", "50")
    results = {run(tmp_path, racy, {"schedule": s, "quantum": 30}).exit_code for s in range(1, 12)}
    assert run(tmp_path, racy).exit_code == 200        # plain round-robin: long turns, no loss
    assert min(results) < 200                           # some schedules lose updates


DEADLOCK = r"""
; two threads take two futex locks in opposite orders
global _start
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000
section .text
_start:
    mov eax, 56
    mov edi, CLONE
    lea rsi, [stack + 4096]
    xor edx, edx
    xor r10d, r10d
    xor r8d, r8d
    syscall
    test rax, rax
    jz other
    lea rdi, [a]
    lea rsi, [b]
    call two
    mov eax, 231
    xor edi, edi
    syscall
other:
    lea rdi, [b]
    lea rsi, [a]
    call two
    mov eax, 60
    xor edi, edi
    syscall
two:                            ; lock rdi, (pause), lock rsi, unlock both
    push rbx
    push r12
    sub rsp, 8
    mov rbx, rdi
    mov r12, rsi
    call lock
    mov ecx, 200
.spin: loop .spin
    mov rdi, r12
    call lock
    mov dword [r12], 0
    mov dword [rbx], 0
    add rsp, 8
    pop r12
    pop rbx
    ret
lock:                           ; a futex lock: 0 free, 1 taken
    mov eax, 1
    xchg eax, [rdi]
    test eax, eax
    jz .got
    push rdi
    mov eax, 202
    xor esi, esi
    mov edx, 1
    xor r10d, r10d
    syscall
    pop rdi
    jmp lock
.got:
    ret
section .bss
alignb 4
a: resd 1
b: resd 1
stack: resb 4096
"""


def test_deadlock_is_reported(tmp_path):
    m = run(tmp_path, DEADLOCK.replace("lock:", "lock_:").replace("call lock", "call lock_")
            .replace("jmp lock", "jmp lock_"), {"quantum": 50})
    assert m.state == "fault" and "deadlock" in m.fault and "thread" in m.fault, m.fault
