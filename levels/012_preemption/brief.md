# Level 12 — Preemption

*Cooperative multitasking works until one program doesn't cooperate. Then the
kernel needs a way to take the CPU back.*

## The task

Level 13's tasks took turns only when they called `sched_yield`. A task in a long loop
held the CPU until it finished, and everyone else waited. Now the **APIC timer**
interrupts every `period` counts, and its handler switches to the next task. That's
**preemption**. The tests run tasks that never yield:

- a long calculation as task 0, and shorter ones after it, which must all finish *before* it;
- tasks that keep patterns in all 15 registers and the carry flag while they're preempted
  hundreds of times, and check them all the time;
- a mix, with tasks that also yield.

Output order now depends on timing, so the game checks each task's own lines, in order,
and that everyone exits.

Everything from level 13 is in the starter, working, along with the timer, set up and wired to
vector 0x40. Yours: the **timer handler**.

## Lesson: an interrupt is not a call

At a `sched_yield` the task *called* the kernel. Like any call, it expects rax, rcx and
r11 to change and the rest to be kept, which is what switch_to keeps. A timer interrupt can
land between *any* two instructions: in the middle of a calculation, with every register
holding something. The CPU saves rip, cs, rflags, rsp and ss. Everything else is the
handler's job:

```
timer:
    push rax, rbx, rcx, rdx, rsi, rdi, rbp, r8 … r15    ; all of it
    EOI
    call schedule       ; the same one sched_yield uses: switch_to someone else
    pop r15 … rax
    iretq               ; ...and when this task's turn comes, it continues
```

The task never knows it stopped.

## Lesson: one more thing that's per task

The **gs base** is the program's own (`arch_prctl`), and lives in a register of the CPU,
not in memory. The timer only arrives from ring 3 (interrupts are off inside this kernel),
so at that moment GS_BASE is the task's: save it across `schedule` as sched_yield does.

## Gate

Nobody starves, every register survives, everyone finishes.
