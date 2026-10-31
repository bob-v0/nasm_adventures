# Level 151 — Bug: Off by One ◆

*There are two hard problems in computer science: naming things, cache
invalidation, and off-by-one errors.*

## Symptoms

Three routines, three wrong answers, each wrong by exactly one:

- **A** copies a buffer and writes one byte past the end of the destination.
- **B** sums an array, but the sum includes a value that isn't in the array and
  misses one that is.
- **C** shifts a buffer and then fills a second buffer. The fill buffer looks fine
  in some runs, but the first buffer comes out corrupted.

## The classic shapes

- **Fencepost:** a 10-metre fence with a post every metre needs 11 posts, not 10.
  Counting the gaps and counting the boundaries give answers that differ by one.
- **Inclusive vs exclusive:** `for i in [0, n)` stops *before* n. In assembly that's
  `jae` (or `jge`) at the top, not `ja`.
- **Count vs index:** an array of m elements has indexes 0 … m−1. Counting down from m
  needs `[base + rcx*8 - 8]`, or a loop that stops at −1.
- **Leaked state:** a flag (like DF) or register set for one routine is still in
  effect in the next. Each routine should leave the machine as it found it.

```
index:    0    1    2    3        m = 4 elements
        [ a ][ b ][ c ][ d ]      valid indexes: 0 .. 3
                             ^
                             index 4 = m is one past the end
```

## How to hunt

Run the smallest cases: n = 0, m = 1. Count iterations in {{debug}} (**line ▶▶** steps
a whole line). Compare memory before and after; the tests put random bytes
everywhere, so an extra write shows up.

## Gate

Fix all three, changing at most **3 lines**. DF must be 0 at the end.
