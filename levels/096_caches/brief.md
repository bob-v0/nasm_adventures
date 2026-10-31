# Level 96 — Caches

*Memory is 200 cycles away. Caches hide that, as long as you play by their rules.*

## Lesson: lines

Memory moves to and from the caches in **lines** of 64 bytes. Touch one byte, and the
whole line comes in. Use the other 63 soon and they're free (**spatial locality**); come
back to the line soon and it's still there (**temporal locality**).

Writes work the same way. To change 8 bytes, the CPU brings in the whole line. A line
you've written is **dirty**: when it's pushed out of the cache, it has to be written
back, which costs another transfer.

The game's CPU: L1 holds 32 KiB (512 lines), L2 1 MiB, then memory.

## Lesson: sets and conflicts

A cache isn't one big bag of lines. L1 is split into **64 sets of 8 lines** (it's
8-way **set-associative**). A line can only go in one set, chosen by bits 6–11 of its
address, and each set holds at most 8 lines.

So the addresses you use decide how much of the cache you get. Addresses 4096 bytes
apart all land in the same set. Addresses 1024 bytes apart cycle through just 4 sets
(1024 bytes is 16 lines, and 64 / 16 = 4). Walk memory with a stride like that and only
a handful of sets do all the work: lines get evicted while the rest of the cache sits
empty. Those are **conflict misses**.

## Lesson: blocking

Transposing reads `src` along rows. That's fine: 8 elements per line, in order, and the
prefetcher sees it coming. But it writes `dst` down columns: each store touches a new
line, uses 8 of its 64 bytes, and moves on. With `n = 128` the column stride is 1024
bytes, so those lines fight over 4 sets, and they're evicted (and written back) long
before you come back for the next column.

**Blocking** (or tiling) changes the order of the work, not the work itself: transpose
one 8×8 tile at a time. A tile touches 8 lines of `src` and 8 of `dst`. They all stay in
L1 until the tile is done, and every line is used completely.

![Writing dst column by column versus one 8×8 tile at a time](transpose.svg)

Matrix multiplication, image filters, databases and compilers' loop tiling all rely on
this.

## Gate

`ring_transpose(dst, src, n)` writes the transpose of an `n × n` matrix of qwords (stored
row by row) into `dst`, for any `n` up to 128 (not always a multiple of 8). For
`n = 128` (and `n = 64`) it must take under **2.5 cycles per element** on the game's
CPU. Both matrices start in L2, as if the caller had just written them.
