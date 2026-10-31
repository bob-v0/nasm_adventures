# Level 7 — SMP

*Every PC since the 2000s has had several cores, and every kernel so far in this game
has used one. The others have been waiting since power-on for someone to wake them.*

## The task

Wake every CPU. Each says hello once, in whatever order they get there, and when all
have, the first CPU says how many did:

```
hello from apic id 0
hello from apic id 2
hello from apic id 1
hello from apic id 3
4 cpus said hello
```

The game boots 2 to 8 CPUs, including two sockets of three cores (APIC ids 0, 1, 2, 4,
5, 6). It checks that every CPU's line is there, whole, and the count at the end.

The starter counts the CPUs for you (from the MADT, as in level 9) and has a delay, a
lock for the serial port, a GDT and room for the stacks. Yours: `hello`, the trampoline,
waking the others, and `ap_entry`.

## Lesson: waking a CPU

At reset one CPU, the **BSP** (bootstrap processor), runs the firmware and your kernel.
The others, the **APs** (application processors), wait until another CPU sends them
**IPIs**: inter-processor interrupts. A CPU sends one by writing its local APIC's
**ICR** (interrupt command register): the destination in the high dword (offset 0x310
from the APIC's base, 0xFEE00000), then the command in the low dword (0x300), which sends
it. To wake the others:

1. **INIT**: get ready. Then wait 10 ms.
2. **STARTUP** (a SIPI, startup IPI) with a vector *v*: start executing at physical
   address *v* × 4096, in **real mode**. Send it twice, 200 µs apart: the second is for
   CPUs that missed the first.

```
0x000C4500   INIT, to everyone but me
0x000C4608   STARTUP, to everyone but me, vector 8 (start at 0x8000)

bits 0-7     the vector (STARTUP's page)
bits 8-10    delivery mode: 101 INIT, 110 STARTUP
bit 14       level: assert
bits 18-19   shorthand: 11 = everyone but me (the high dword's destination is ignored)
```

After each, wait until the ICR's bit 12 (delivery status) clears: the starter's
`wait_sent`.

![INIT, then two STARTUPs; each AP runs the trampoline into the kernel](smp.svg)

So an AP starts like the PC did back in Arc XI: 16-bit, at a page you chose. The code there
is the **trampoline**: a few instructions that load the GDT, enter protected mode, and jump
into the kernel. You copy it to that page, so it must work at an address it wasn't
linked for.

## Lesson: per-CPU data, and one printer

Every AP runs the same code at the same time, so each needs a **stack of its own**. Each
takes a number from a shared counter with `lock xadd` (atomic: no two get the same) and
uses the stack with that number.

And they all print to one serial port. Without a lock, CPUs printing at once produce
`hello from apic idhello from apic id…`. The starter's `lock_serial` / `unlock_serial`
(a spinlock: `xchg` is atomic) make each line one CPU's.

## Gate

Every CPU's hello, whole, and the right count, on every machine.
