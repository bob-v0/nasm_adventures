# Level 22 — Page Faults

*A program asks for a gigabyte and uses a few kilobytes. A page fault is how the kernel
avoids paying for the rest.*

## The task

The kernel has a **lazy region**: 64 GiB of virtual memory starting at
0xFFFFC00000000000, reserved but not mapped. Nothing backs it until it's used.

The first access to a page there is a page fault. Your handler gives that page a fresh
frame, maps it, and returns. The CPU then runs the faulting instruction again, and this
time it works. The program never notices.

Two functions are yours:

- `lazy_fault`: called by the page fault handler with rax = CR2 and rdx = the error code.
  If the fault is a missing page in the lazy region, map a fresh frame there and set CF
  (the handler then returns to retry). Otherwise clear CF, and the handler reports it as
  in level 24. The handler has saved rax, rcx, rdx, rsi and rdi; keep everything else.
- `map_page(rdi = virtual page, rsi = physical frame)`: map one 4 KiB page, writable,
  kernel-only, creating the PDPT, PD and PT on the way if they don't exist yet.

`alloc_frame` (given) hands out frames already zeroed.

The game's test reads and writes all over the region, with some pages close together
and some gigabytes apart. It checks every value: fresh memory reads as 0, and written
memory keeps its value. Then it walks your page tables itself. Exactly the pages it touched
must be mapped, no more, each on a frame of its own. RAM starts out full of junk in this
level, as it would after a reboot, so zeroing matters. A null pointer, or an access past
the end of the region, must still be reported, not mapped.

## Lesson: what the page fault says

| | |
|---|---|
| CR2 | the address that was accessed |
| error code bit 0 | 0: the page isn't there · 1: it is, but the access isn't allowed |
| bit 1 | a write |
| bit 2 | from user mode |
| bit 4 | an instruction fetch |

A missing page in a region you're responsible for is work to do. A present page, or an
address outside every region, is a bug, and gets reported.

## Lesson: building tables as you go

The walk is the same one the CPU does (level 26), except that where an entry isn't
present, you make the table: take a zeroed frame (a table full of junk would map junk)
and store frame | present | writable in the entry. Then go down into it. RAM is below
1 GiB here, and the identity map covers it, so a table's physical address is also a
pointer you can use.

![map_page: walk down, creating what's missing](demand.svg)

After changing a mapping, `invlpg [address]` drops any stale translation the CPU may
have cached for it (the TLB). Strictly speaking a page that was not present can't be
cached, but it's a good habit. Level 17 is about what happens without it.

## Gate

Every test's reads, writes and table walk as expected, and the stray accesses reported.
