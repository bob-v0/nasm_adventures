# Level 0 — Ring 0 ★

*No BIOS calls once you're running, no multiboot, no one CPU at a time. Your
bootloader, your kernel, every core, your programs. This is the bottom.*

## The task

One disk image, all yours:

1. **Your bootloader** (Arc XI). The BIOS loads sector 0. From there you load the
   rest: the kernel (right after your second stage), and the game's data from sector
   2048 (a header, the filesystem image, the shell's script). You collect the memory map
   and build the boot information block your kernel already knows how to read, the one
   QEMU's multiboot loader used to make. Then protected mode, the kernel at 1 MiB, and
   the jump.
2. **Your kernel, on every CPU.** Level 10's kernel is in the starter, as it was: one
   CPU. Wake the others (level 7, with a trampoline that goes on to long mode), give
   each its own per-CPU data, TSS and system-call setup, and run **one scheduler** for
   all of them: any process on any CPU.
3. **Your programs, at the same time.** Besides Tiny Shell (running its script, as in
   level 10), every program in `/init` starts at boot, on whichever CPU is free: the
   game's `hello`, and two programs from Arc I, `speak` (level 175) and `boot` (level
   172). Each program's lines come out whole, with its name in front; the shell's have
   no prefix:

```
[speak] Hello, operator!
[hello] hello world
[speak] warning: the walls have ears
[speak] exited with status 29
[hello] exited with status 0
[boot] boot: cpu ok
...
1
1
y
shell exited with status 0
all done: user code ran on 4 cpus
```

When the shell and every program have ended, the kernel says on how many CPUs user code
ran, and every CPU stops.

The order between programs depends on timing. Each program's own lines, and the
shell's, must be exactly right and in order. The game runs your OS on 1, 2 and 4 CPUs,
most tests with the CPUs truly in parallel.

## Lesson: one kernel, many CPUs

![Every CPU runs the same scheduler; one lock guards the kernel's state](ring0.svg)

The simplest correct design is the one Linux started with: a **big kernel lock**, one
spinlock around the whole kernel. A CPU takes it on every entry from ring 3 (a system
call, a fault) and releases it on every return to ring 3. Kernel code then never runs on
two CPUs at once, and level 10's kernel needs no other change to be safe. Programs still
run on every CPU at once: only the kernel takes turns.

A task that blocks keeps the lock through the switch. Whatever runs next on that CPU
releases it: another task, on its way back to ring 3, or that CPU's **idle task**, a
loop of its own for when nothing is ready.

In the kernel, gs is always *this CPU's* data: the running task, its kernel stack, its
TSS. Swap only at the ring-3 boundary (level 19's lesson). And start nothing until the
other CPUs are ready to compete for it, then create the tasks under the lock: idle CPUs
take ready tasks the moment they appear.

## Gate

Every test: your image boots, the shell's script and all three programs run, at the
same time, and everything ends with `all done`. With more than one CPU in parallel,
programs must have run on at least two of them. You win.
