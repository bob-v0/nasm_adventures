# Level 125 — Heap

*Every `malloc` you've ever called sits on two system calls and a linked list.
Now you write one.*

## Lesson: memory from the kernel

A process gets memory in pages from the kernel:

- **`brk`** (12) moves the end of the *heap*, a region right after your program's data.
  `brk(0)` returns the current end; `brk(addr)` moves it and returns the new end.
- **`mmap`** (9) maps fresh pages anywhere: `mmap(0, len, PROT_READ|PROT_WRITE,
  MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)`. Real allocators use it for big blocks.

Both are slow and work in whole pages. `malloc` exists to hand out small pieces and to
**reuse** what's freed, without asking the kernel every time.

## Lesson: headers and free lists

```
          header (16 bytes)            your block (size rounded up to 16)
        ┌─────────┬──────────┬────────────────────────────────┐
  ...   │  size   │ next free│ ............................... │ ...
        └─────────┴──────────┴────────────────────────────────┘
                              ↑ malloc returns this address (16-byte aligned)
```

`free(p)` finds the header at `p - 16` and pushes the block onto a **free list**. `malloc`
searches the list first (first fit: take the first block big enough) and only grows the
heap when nothing fits. Splitting big free blocks and merging neighbours (coalescing)
fight **fragmentation**, where free memory is chopped into pieces too small to use.

## Gate

Write `malloc(size)` and `free(ptr)` (both `global`):

- every returned pointer must be non-NULL, 16-byte aligned, and not overlap any other
  live block
- `free(NULL)` does nothing
- the usual function contract applies, including stack alignment

The game's `ring_workload` runs hundreds of random mallocs and frees, filling each block
and checking it's intact when freed. The heap (brk growth plus mmaps) may grow to at most
**3 × the peak live bytes + 64 KB**. The workloads allocate much more than that in total,
so a bump allocator that never reuses memory won't fit.

Passing adds `malloc` to your library. Arc V's later levels lean on it.
