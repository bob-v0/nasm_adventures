# Level 24 — 64-bit IDT

*In long mode, an exception without an IDT is a triple fault, and you never find out
why. Give the CPU somewhere to report to.*

## The task

Fill in `init_idt`: an IDT with gates for the 32 exception vectors, and handlers that
print one line each:

```
#UD at 0x0000000000080019
#GP at 0x0000000000080022, error code 0x0000000000000000
#PF at 0x000000000008001d, error code 0x0000000000000002, cr2 0x000000007ffff000
```

That's the name (from the starter's `names` table, 4 bytes each), the rip the CPU pushed,
the error code if the vector has one (`has_error` has a bit per vector), and CR2 for a
page fault. Then halt, except for `#BP` (`int3`), which is a **trap**: report it and
`iretq` back. The test carries on, and the kernel prints `done`.

The game's test is a module the starter copies to 0x80000 and calls. Each test causes one
exception: divide error, invalid opcode, a non-canonical address, page faults (read,
write, a null pointer, executing from the no-execute direct map), a breakpoint, and a
**double fault**.

## Lesson: 64-bit gates

Each gate is 16 bytes, because the handler's address is 64 bits:

| bytes | |
|---|---|
| 0-1 | offset bits 0-15 |
| 2-3 | code segment selector (0x08) |
| 4 | IST: 0, or which IST stack (1-7) |
| 5 | 0x8E: present, ring 0, interrupt gate |
| 6-7 | offset bits 16-31 |
| 8-11 | offset bits 32-63 |
| 12-15 | 0 |

In long mode the CPU always pushes the same frame: ss, rsp, rflags, cs, rip. Some
exceptions push an **error code** on top (8, 10-14, 17, 21, 29, 30). A common trick is
small per-vector stubs that push a 0 where there's no error code, then the vector number,
so one handler sees the same layout every time. `iretq` returns: it pops rip, cs, rflags,
rsp and ss (the error code is yours to remove first).

The page fault's error code says why: bit 0 = the page was present (a protection
violation, not a missing page), bit 1 = a write, bit 2 = from user mode, bit 4 = an
instruction fetch. **CR2** holds the address that was being accessed.

## Lesson: a stack you can trust

The double-fault test sets rsp to an unmapped address and pushes. That's a page fault,
and delivering it means pushing a frame onto the same unmapped stack: another fault, so
a **#DF**. Delivering *that* needs the stack as well. Third fault: reset.

The fix is the **IST** (interrupt stack table): up to seven known-good stacks, kept in
the **TSS**. A gate with an IST index makes the CPU switch to that stack *before* pushing
anything. In long mode the TSS no longer switches tasks. It's just a table of stack
pointers:

| offset | |
|---|---|
| 4 | RSP0: the stack for entering ring 0 from user mode (level 21) |
| 36 | IST1 |
| 44 … 84 | IST2 … IST7 |
| 102 | I/O permission map offset: 104 (none) |

Its descriptor in the GDT is 16 bytes (type 0x89, limit 103, a 64-bit base). The
starter leaves room for it at selector 0x18. Load it with `ltr`.

## Gate

Every exception the game causes, reported exactly, and the double fault survived.
