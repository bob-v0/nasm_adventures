# Level 7 — SMP

*Every PC since the 2000s has had several cores, and every kernel so far in this game
has used one. The others have been waiting since power-on for someone to wake them.*

## The task

Wake every CPU. Each says hello once, in whatever order they get there:

```
hello from apic id 0
hello from apic id 2
hello from apic id 1
hello from apic id 3
4 cpus said hello
```

The game boots 2 to 8 CPUs, including two sockets of three cores (APIC ids 0, 1, 2, 4,
5, 6). It checks every CPU's line is there, whole, and the count at the end.

## Lesson: waking a CPU

At reset one CPU, the **BSP** (bootstrap processor), runs the firmware and your kernel.
The others, the **APs**, wait in a special state until another CPU sends them
**inter-processor interrupts** through its local APIC (the **ICR**, interrupt command
register, at 0x300):

1. **INIT**: get ready. Then wait 10 ms.
2. **STARTUP** (SIPI) with a vector *v*: start executing at physical address *v* × 4096,
   in **real mode**. Send it twice, 200 µs apart: the second is for CPUs that missed the
   first.

![INIT, then two STARTUPs; each AP runs the trampoline into the kernel](smp.svg)

So an AP starts like the PC did back in Arc XI: 16-bit, at a page you chose. The code there
is the **trampoline**: a few instructions that load the GDT, enter protected mode, and jump
into the kernel. It's copied to that page, so it must work at an address it wasn't linked
for.

## Lesson: per-CPU data, and one printer

Every AP runs the same code at the same time, so each needs a **stack of its own**. Each
takes a number from a shared counter with `lock xadd` (atomic: no two get the same) and
uses the stack with that number.

And they all print to one serial port. Without a lock, eight CPUs printing at once
produce `hello from apic idhello from apic id…`. The starter's spinlock (`xchg` is atomic)
makes each line one CPU's.

## Gate

Every CPU's hello, whole, and the right count, on every machine.
