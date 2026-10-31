# Level 21 — Privilege Rings

*Until now every instruction ran with every privilege. A kernel's first job is to
run programs that can't take them.*

## The task

The game's program is copied to 0x400000 (the starter does it). Run it in **ring 3**,
with its stack at 0x600000. It may use its own 2 MiB page and nothing else, and it asks
the kernel for things with `int 0x80`:

| rax | | |
|---|---|---|
| 1 | write | print rdx bytes from rsi on the serial port, then return |
| 60 | exit | print `user program exited with status <rdi>`, then halt |

The tests' programs say hello (`hello from ring 3`: they read the ring from their own
cs), exit with some status, or try what ring 3 mustn't: `cli`, `hlt`, reading or writing
the kernel's memory, `int 0x30`. Those must become exceptions, reported by level 24's
handlers:

```
#PF at 0x0000000000400019, error code 0x0000000000000005, cr2 0xffffffff80100000
```

## Lesson: rings

The CPU's privilege level, **CPL**, is the low two bits of cs: 0 for the kernel, 3 for
programs. Everything privileged checks it:

- **descriptors** have a **DPL** (descriptor privilege level): ring 3 can only load
  segments, and `int n` only through gates, whose DPL is 3;
- **selectors** carry an **RPL** (their low two bits): the ring they're meant for;
- **instructions** like `cli`, `hlt`, `lgdt` and `mov cr3` need ring 0: elsewhere they're #GP;
- **pages**: an access from ring 3 needs the **U** bit in *every* entry of its walk.

So ring 3 needs its own code and data descriptors, the kernel's with DPL 3: data
0x0000F20000000000 at selector 0x18, code 0x0020FA0000000000 at 0x20. (Data comes
first for a reason level 20 will need.) The TSS moves up to 0x28.

## Lesson: going down, coming back

There's no instruction that just says "ring 3". Instead the kernel pretends to return
from an interrupt that came from there: it pushes the frame `iretq` pops (ss, rsp, rflags,
cs, rip) with user selectors (RPL 3), then executes `iretq`.

![iretq into ring 3, int 0x80 back to ring 0](rings.svg)

Coming back is an interrupt: `int 0x80` through a gate with **DPL 3** (type 0xEE), the
only gate ring 3 may use. A gate with DPL 0 (like `int 0x30` here) is a #GP. An interrupt
from ring 3 can't push its frame on the user's stack, which the program controls. The
CPU switches to the stack in the TSS's **RSP0** first. That's the TSS's other job (level
24 used its IST).

## Gate

Every program's output, exit and forbidden attempts exactly as expected.
