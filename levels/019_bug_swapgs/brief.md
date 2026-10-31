# Level 19 — Bug: swapgs Confusion ◆◆◆◆

*It only goes wrong when a timer interrupt lands in one particular window: during a
system call, after interrupts come back on. That's a few hundred instructions in every
few thousand.*

## Symptoms

Level 20's kernel has grown two things real kernels have. The **APIC timer** interrupts
every `period` counts, and its handler counts ticks in the per-CPU data, through gs.
And **system calls re-enable interrupts** once they're on the kernel stack, so a long
system call doesn't hold off the timer. Linux does the same.

The program sets its own gs base, computes, writes 16 lines, then checks its data at
gs:16:

```
round 16
my data changed!
user program exited with status 1
```

Nothing crashed. With some periods it's fine, with others the data has changed.

## Background: two gs bases

From level 20: the CPU holds two gs bases, and `swapgs` exchanges them. In ring 3 the
live one is the program's. After a kernel entry swaps, it's the kernel's. The swap has no
idea which state it's in: doing it twice puts you back where you started.

So every kernel entry point has to know: was the live gs the program's when I came in?
For `syscall`, always (only ring 3 executes it). For an **interrupt**, it depends on
where it interrupted:

![An interrupt from ring 3 must swap; one from inside the kernel must not](swapgs.svg)

The CPU tells you. The frame it pushed holds the interrupted **cs** at [rsp + 8], and
its low two bits are the ring that was running.

## Gate

Find a period that corrupts the program's data (`;! witness period = N`), then fix the
kernel: the program's data intact for every period, and the timer still ticking.
At most 8 changed lines.
