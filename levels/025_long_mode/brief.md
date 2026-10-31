# Level 25 — Enter Long Mode

*Four control bits, one far jump, and the CPU is a 64-bit machine. Get the order
wrong and it resets before it can tell you why.*

## The task

The kernel builds level 26's page tables (that code is in the starter). Now switch them
on, enter 64-bit mode, and continue in the **higher half**: at 0xFFFFFFFF80000000 + the
address the code was linked at. That's the same physical memory through the second
mapping. Move the stack there too, and print where the code is running:

```
hello from long mode, at 0xffffffff801000ec
```

Then `cli`, `hlt`. The game checks the CPU's state at the halt: paging on, long mode
active, 64-bit code, RIP in the higher half.

## Lesson: the switch

![Entering long mode: four steps, then the far jump](switch.svg)

1. **CR4.PAE** (bit 5): page table entries are 8 bytes.
2. **CR3** = the PML4's physical address.
3. **EFER.LME** (bit 8; MSR 0xC0000080): long mode *enable*. Set **NXE** (bit 11) too,
   because the direct map's NX bit is a reserved bit, and a page fault, without it.
4. **CR0.PG** (bit 31): paging on. With LME set, this is the moment long mode becomes
   *active*: the CPU sets EFER.LMA.

The order matters. Paging on without LME gives 32-bit PAE paging, which reads your
PML4 as a different, smaller table and page-faults on the very next instruction. The
fault explainer will show you one.

## Lesson: compatibility mode

Long mode is active, but the CPU is still running your 32-bit code: CS still holds the
32-bit segment. This in-between state is **compatibility mode**, and it's how 64-bit
operating systems run old 32-bit programs.

The way out is a far jump to a **64-bit code segment**: a GDT entry with the **L** bit
(bit 53). Base and limit no longer matter in 64-bit mode:

```
gdt:    dq 0
        dq 0x00209A0000000000   ; code: present, ring 0, L
        dq 0x0000920000000000   ; data: present, writable
```

`lgdt` it, then `jmp 0x08:long_mode`, with `bits 64` before `long_mode:`.

## Lesson: the higher half

Your code was linked at 1 MiB, and the identity map is what lets it keep running there.
The higher-half mapping shows the same bytes at 0xFFFFFFFF80000000 + 1 MiB. A jump through
a register (`mov rax, HIGH + label`, `jmp rax`) carries on at the same instruction, high.
Real kernels then remove the identity map, and user programs get the low half.

`lea rax, [rel label]` computes label's address from RIP, so it's the address the
code is really running at, not the one it was linked at.

## Gate

64-bit mode, in the higher half, saying where it is, on every CPU model the game tries.
