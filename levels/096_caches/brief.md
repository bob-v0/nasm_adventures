# Level 96 — Caches

*Memory is 200 cycles away. Caches hide that, as long as you play by their rules.*

## Lesson: lines

Memory moves to and from the caches in **lines** of 64 bytes. Touch one byte, and the
whole line comes in. Use the other 63 soon and they're free (**spatial locality**); come
back to the line soon and it's still there (**temporal locality**). A write is no
different: to change 8 bytes the CPU brings in the whole line, and a line you've written
is **dirty**: when it's pushed out, it has to be written back.

The game's CPU: L1 holds 32 KiB (512 lines), L2 1 MiB, then memory.

## Lesson: sets and conflicts

A cache isn't one big bag of lines. L1 is split into **64 sets of 8 lines** (8-way
**set-associative**): a line can only go in the set given by bits 6–11 of its address.
Addresses 4096 bytes apart always land in the same set, and so do 1024 bytes apart, a
quarter of the time… Walk with a stride like that and you're using a handful of sets.
You get misses although the cache is mostly empty: **conflict misses**.

## Lesson: blocking

Transposing reads `src` along rows (fine: 8 elements per line, sequential, prefetched)
and writes `dst` down columns: each store touches a new line, uses 8 of its 64 bytes,
and moves on. With `n = 128` the column stride is 1024 bytes, so those lines fight over 4
sets and are evicted (and written back) long before you come back for the next column.

**Blocking** (tiling) changes the order, not the work: transpose one 8×8 tile at a time.
A tile touches 8 lines of `src` and 8 of `dst`, which all stay in L1 until the tile is
done, and every line is used completely. Matrix multiplication, image filters, databases
and compilers' loop tiling all rely on this.

## Gate

`ring_transpose(dst, src, n)` writes the transpose of an `n × n` matrix of qwords (stored
row by row) into `dst`. For any `n` up to 128 (not always a multiple of 8). For
`n = 128` it must take under **2.5 cycles per element** on the game's CPU; the matrices
start in L2, as if the caller had just written them.
