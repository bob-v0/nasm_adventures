# Level 18 — Virtual Memory Manager

*Two programs both believe they live at 0x400000, and both are right. Each has an
address space of its own.*

## The task

Every module the game gives the kernel is a program, linked at 0x400000. The kernel runs
them one after another, each in its own **address space**:

- its own PML4, with its own low half, the program's;
- the kernel's half (PML4 entries 256-511) shared, the same in every space;
- memory on demand (level 22, now for programs): touch a page in your half, get a fresh one;
- when the program exits, or is killed for a fault, **every frame it had comes back**.

The tests run programs that check what isolation promises. One writes a secret, and the
next one, at the same address, must see fresh memory. One reads the kernel's memory and
is killed, while the next one runs normally. 24 programs each use 4 MiB in a machine of
48 MiB, which only works if memory comes back. And one recurses through 100 KiB of
stack that is never allocated up front.

The process loop, loading and the frame allocator are in the starter. Yours:
`new_space`, `free_space`, `map_user` and `user_fault`.

## Lesson: what's shared, what's not

![Two address spaces: private low halves, one kernel half](spaces.svg)

`mov cr3, rax` switches the whole view of memory in one instruction. Everything the
kernel needs has to look the same in every space: its code and data in the higher half,
and the **direct map**. The kernel's first 4 MiB also stay mapped in the low half,
supervisor-only, because this kernel still uses a few low addresses.

The low half is the program's now, so the kernel can't assume physical address x is
mapped at x anymore. The **direct map** is how it reaches physical memory from now on:
physical x is at DIRECT + x (0xFFFF800000000000 + x) in every space. Page tables are made
of frames, so every table the kernel reads or writes goes through it.

## Lesson: tearing down

An address space owns its pages and its tables. Freeing it means walking the low half
the way the CPU does: the PML4's entries 0-255, each PDPT, PD and PT, giving back the
pages, then each table. Skip what's shared: the kernel's two PD entries are in every space,
so freeing them would hand out the kernel's own memory. Do it with CR3 pointing somewhere
else: the loop switches back to the kernel's PML4 first.

## Gate

Every test's programs, outputs and kills, with memory to spare at the end.
