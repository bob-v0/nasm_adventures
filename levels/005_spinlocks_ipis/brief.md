# Level 5 — Spinlocks & IPIs

*One CPU can't race with itself. Four can, and they do, in places that look perfectly
innocent.*

## The task

Every CPU now runs at the same time, truly in parallel. (The game runs these tests on
QEMU's multi-threaded mode, so the CPUs really overlap.) Two jobs:

1. **Shared work.** 4000 jobs, shared by every CPU: each takes the next unclaimed one,
   computes its value, adds it to a shared total. Every job exactly once, the total right.
2. **A shared page, remapped.** The first CPU points a page, WINDOW, at a new frame,
   round after round, while the others keep reading it. After each remap, *every* CPU
   must see the new frame.

```
jobs done: 4000, total 131058610
round 1: every cpu sees 1
...
round 8: every cpu sees 8
```

Yours: the lock, `work`, and the shootdown (`shoot_down` and its interrupt handler).

## Lesson: spinlocks

`inc dword [next_job]` looks like one step. It's three, read, add, write, and two CPUs
can both read 41 and both write 42. A **spinlock** makes a sequence of steps one CPU's at a
time:

```
lock:   mov edx, 1
        xchg edx, [the_lock]    ; atomic: old value out, 1 in
        test edx, edx
        jz got_it               ; it was 0: mine
.spin:  pause                   ; it was 1: wait until it looks free...
        cmp dword [the_lock], 0
        jne .spin
        jmp lock                ; ...then really try again
unlock: mov dword [the_lock], 0
```

## Lesson: the TLB is per CPU

Level 17's stale TLB, now with four CPUs. When one CPU changes a page table entry,
`invlpg` cleans *its own* TLB. The others may still hold the old translation, and nothing
in the hardware tells them. So the kernel tells them: an **inter-processor interrupt**
with a vector of your choice, to everyone but yourself. Each handler runs `invlpg` and
acknowledges, and the CPU that changed the mapping waits for every acknowledgement before
carrying on. That's a **TLB shootdown**.

![A TLB shootdown: change the entry, IPI the others, wait for every ack](shootdown.svg)

## Gate

The right total and every round seen by every CPU, on every machine.
