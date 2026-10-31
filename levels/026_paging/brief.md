# Level 26 — 4-Level Paging

*In long mode every address goes through page tables. There is no switching them off.
So before the switch, build the tables.*

## The task

Build page tables for three regions, each a view of the first 1 GiB of physical memory:

| region | virtual | physical | |
|---|---|---|---|
| identity | 0 + x | x | except the first 4 KiB: a null pointer must fault |
| higher half | 0xFFFFFFFF80000000 + x | x | where kernels live (the top 2 GiB) |
| direct map | 0xFFFF800000000000 + x | x | **no-execute**: data only |

All writable, none reachable from user mode, and nothing else mapped. Halt with eax =
the PML4's physical address. Paging stays off in this level, because 32-bit code can't use
4-level tables. The game walks your tables exactly as the CPU will in level 25.

## Lesson: four tables deep

A 64-bit virtual address really has 48 bits that count. They split into four 9-bit
indexes and a 12-bit offset:

![A virtual address is four table indexes and an offset](walk.svg)

Each table is 4 KiB: 512 entries of 8 bytes, at a 4 KiB-aligned address. CR3 holds the
**PML4**'s address. Its entry selects a **PDPT**, whose entry selects a **PD**, whose
entry selects a **PT**, whose entry is the 4 KiB page. An entry is the physical address of
the next thing, with flags in the bits an aligned address doesn't need:

| bit | | |
|---|---|---|
| 0 | P | present: without it, any access is a page fault |
| 1 | W | writable |
| 2 | U | user mode may use it (not here: this is all kernel memory) |
| 7 | PS | in a PD entry: this *is* a 2 MiB page; stop here |
| 63 | NX | no-execute (needs EFER.NXE, level 28) |

A page's permissions are those of every entry on its path: writable only if all are
writable, no-execute if any says NX.

## Lesson: the shape of the address space

The 48 bits are sign-extended to 64: bits 48-63 must all equal bit 47. Addresses
that break the rule (*non-canonical*) fault before any table is read. So the address space
is two halves, with a huge hole between them: 0 to 0x00007FFFFFFFFFFF for programs, and
0xFFFF800000000000 up for the kernel. That's why the kernel's addresses look the way they
do.

**2 MiB pages** save a whole level: a PD entry with PS set maps 2 MiB directly, and the
page must start at a multiple of 2 MiB. 1 GiB of them is a single PD. The first 2 MiB is
the exception here, because the null page needs a hole of 4 KiB. That one PD entry points
to a real PT instead.

And tables can be **shared**: an entry only says where the next table is, so several
entries can point at the same table. All three regions can use one PD, and the identity
map and the direct map can even share a PDPT (PML4 entries 0 and 256 pointing at the same
one); the direct map's NX then goes on its PML4 entry. Sharing the PD also shares its
4 KiB hole, so the other two regions lose their first 4 KiB as well. That's fine: the
game doesn't look there.

## Gate

For every address the game tries, the right physical address and permissions, or
nothing.
