"""The game's task runtime (ring/runtime/rt.asm) on the emulated kernel."""

from pathlib import Path

import pytest

from ring.build import build
from ring.emu import Machine
from ring.kernel import Injection, Kernel

RT = Path(__file__).resolve().parent.parent / "ring" / "runtime" / "rt.asm"

WORKERS = r"""
; 5 workers: lock, read counter, yield (inside the lock!), write counter+1, unlock, sleep.
; A 6th task is cancelled while it waits for the lock. Exit status: counter * 10 + stuck.
global _start
extern rt_spawn, rt_run, rt_yield, rt_lock, rt_unlock, rt_sleep, rt_cancel, rt_current
section .text
_start:
    mov ebx, 5
.spawn:
    lea rdi, [worker]
    mov rsi, rbx
    call rt_spawn
    dec ebx
    jnz .spawn
    lea rdi, [victim]
    xor esi, esi
    call rt_spawn
    mov [victim_task], rax
    lea rdi, [canceller]
    xor esi, esi
    call rt_spawn
    call rt_run
    mov rbx, rax
    imul rdi, [counter], 10
    add rdi, rbx
    add rdi, [victim_saw]
    mov eax, 60
    syscall

worker:
    push rbx
    mov rbx, rdi
    lea rdi, [mtx]
    call rt_lock
    mov rax, [counter]
    push rax
    sub rsp, 8
    call rt_yield               ; others run, but none can get the lock
    add rsp, 8
    pop rax
    inc rax
    mov [counter], rax
    lea rdi, [mtx]
    call rt_unlock
    mov rdi, rbx
    call rt_sleep               ; 1..5 ms
    pop rbx
    ret

victim:                         ; waits for the lock and gets cancelled while waiting
    sub rsp, 8
    lea rdi, [mtx]
    call rt_lock
    cmp rax, -125
    jne .got
    mov qword [victim_saw], 100 ; exit status gets +100: it saw the cancellation
    add rsp, 8
    ret
.got:
    lea rdi, [mtx]
    call rt_unlock
    add rsp, 8
    ret

canceller:
    sub rsp, 8
    call rt_yield
    mov rdi, [victim_task]
    call rt_cancel
    add rsp, 8
    ret

section .bss
mtx:         resq 3
counter:     resq 1
victim_task: resq 1
victim_saw:  resq 1
"""


def run(tmp_path, source, inject=None, steps=3_000_000):
    (tmp_path / "s.asm").write_text(source)
    b = build(tmp_path / "s.asm", tmp_path / "b", "program", helpers=[RT])
    m = Machine(b, kernel=Kernel(inject=Injection.from_dict(inject or {}, "t")))
    m.run(steps)
    return m


@pytest.mark.parametrize("schedule", range(0, 12))
def test_lock_sleep_cancel_under_many_schedules(tmp_path, schedule):
    m = run(tmp_path, WORKERS, {"schedule": schedule})
    assert m.state == "exited", m.fault
    # 5 increments; nobody stuck; the victim is either cancelled while waiting (+100) or
    # got the lock before the canceller ran (+0, and its cancel flag is harmless).
    assert m.exit_code in (50, 150), (m.exit_code, bytes(m.stderr))


def test_cancel_at_an_await_point(tmp_path):
    """The grader can cancel whichever task reaches the nth await."""
    m0 = run(tmp_path, WORKERS)
    n = len(m0.kernel.awaits)
    assert n > 10
    outcomes = set()
    for k in range(1, n + 1):
        m = run(tmp_path, WORKERS, {"cancel_at": k})
        assert m.state == "exited", (k, m.fault)
        outcomes.add(m.exit_code)
    # This worker ignores rt_lock's -125 and goes on without the lock: cancelling it at
    # the wrong await loses increments (the bug level 103 is about).
    assert any(o % 100 < 50 for o in outcomes), outcomes


STUCK = r"""
global _start
extern rt_spawn, rt_run, rt_park
section .text
_start:
    lea rdi, [sleeper]
    xor esi, esi
    call rt_spawn
    call rt_run
    mov rdi, rax
    mov eax, 60
    syscall
sleeper:
    sub rsp, 8
    call rt_park                ; nobody will ever unpark it
    add rsp, 8
    ret
"""


def test_stuck_tasks_are_reported(tmp_path):
    m = run(tmp_path, STUCK)
    assert (m.state, m.exit_code) == ("exited", 1)
    assert b"waiting forever" in bytes(m.stderr)
