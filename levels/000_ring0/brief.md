# Level 0 — Ring 0 ★

*No BIOS calls once you're running, no multiboot, no one CPU at a time. Your
bootloader, your kernel, every core, your programs. This is the bottom.*

## The task

One disk image, all yours:

1. **Your bootloader** (Arc XI). The BIOS loads sector 0. From there you load the
   rest: the kernel, and the game's data from sector 2048 (a header, the filesystem
   image, the shell's script). You collect the memory map and build the boot information
   block your kernel already knows how to read, the one QEMU's multiboot loader used to
   make. Then protected mode, the kernel at 1 MiB, and the jump.
2. **Your kernel, on four CPUs.** Level 10's kernel is in the starter, as it was: one CPU.
   Wake the others (level 7, with a trampoline that reaches long mode), give each its own
   per-CPU data, TSS and system-call setup, and run **one scheduler** for all of them:
   any process on any CPU.
3. **Your programs, at the same time.** Besides Tiny Shell (running its script, as in level
   10), every program in `/init` starts at boot, on whichever CPU is free: the game's
   `hello`, and level 175's and level 172's programs from Arc I. Each program's lines come
   out whole, with its name in front:

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

The order between programs depends on timing. Each program's own lines, and the
shell's, must be exactly right and in order. The game runs your OS on 1 to 4 CPUs, most
tests with the CPUs truly in parallel.

## Lesson: one kernel, many CPUs

![Every CPU runs the same scheduler; one lock guards the kernel's state](ring0.svg)

The simplest correct design is the one Linux started with: a **big kernel lock**. A
CPU takes it on every entry from ring 3 (a system call, a fault) and releases it on every
return. Kernel code then never runs on two CPUs at once, and level 10's kernel needs no
other change to be safe. A task that blocks keeps the lock through the switch. The
next task on that CPU, or that CPU's **idle task**, is the one that releases it.

In the kernel, gs is always *this CPU's* data: the running task, its kernel stack, its
TSS. Swap only at the ring-3 boundary (level 19's lesson). And don't let anything new
start before the other CPUs are ready to compete for it, with the tasks created under
the lock, since idle CPUs take ready tasks the moment they appear.

## Gate

Every test: your image boots, the shell's script and all three programs run, at the
same time, on as many CPUs as the machine has, and everything ends: `all done`.
You win.
