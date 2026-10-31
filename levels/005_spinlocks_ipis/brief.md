# Level 5 — Spinlocks & IPIs

*One CPU can't race with itself. Four can, and they do, in places that look perfectly
innocent.*

## The task

Every CPU now runs at the same time, truly in parallel. (Until now QEMU ran the CPUs
one at a time, taking turns; these tests use its multi-threaded mode, so the CPUs
really overlap.) Two jobs, on 2 to 8 CPUs:

1. **Shared work.** 4000 jobs, shared by every CPU: each CPU takes the next unclaimed
   one, computes its value, adds it to a shared total. Every job exactly once, the total
   right.
2. **A shared page, remapped.** The first CPU (the BSP) points a page, WINDOW, at a new
   frame, round after round, while the others keep reading it. After each remap,
   *every* CPU must see the new frame.

```
jobs done: 4000, total 131058610
round 1: every cpu sees 1
...
round 8: every cpu sees 8
```

Yours: the lock (`lock_jobs` / `unlock_jobs`), `work`, and the shootdown
(`shoot_down` and its interrupt handler, `shootdown`). Waking the CPUs, paging, the
rounds and the report are done.

## Lesson: spinlocks

`inc dword [next_job]` looks like one step. It's three, read, add, write, and two CPUs
can both read 41 and both write 42. A **spinlock** makes a sequence of steps one CPU's at a
time:

```
take:   mov edx, 1
        xchg edx, [the_lock]    ; atomic: old value out, 1 in
        test edx, edx
        jz .mine                ; it was 0: mine
.spin:  pause                   ; it was 1: wait until it looks free...
        cmp dword [the_lock], 0
        jne .spin
        jmp take                ; ...then really try again
.mine:  ret

release:
        mov dword [the_lock], 0 ; a plain store is enough on x86
        ret
```

## Lesson: the TLB is per CPU

Level 17's stale TLB, now with several CPUs. When one CPU changes a page table entry,
`invlpg` cleans *its own* TLB. The others may still hold the old translation, and nothing
in the hardware tells them. So the kernel tells them: an **IPI** (inter-processor
interrupt, level 7) with a vector of your choice, here SHOOTDOWN, sent to everyone but
yourself. Each CPU's handler runs `invlpg` and acknowledges, by counting itself in a
shared counter (and, as any interrupt handler, with an EOI to its APIC). The CPU that
changed the mapping waits until every other CPU has counted itself before carrying on.
That's a **TLB shootdown**.

![A TLB shootdown: change the entry, IPI the others, wait for every ack](shootdown.svg)

## Gate

The right total and every round seen by every CPU, on every machine.
