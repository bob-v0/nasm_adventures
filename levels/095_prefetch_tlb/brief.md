# Level 95 — Prefetch & TLB

*A linked list in memory is a treasure hunt: every clue tells you where the next one
is, and each one takes 200 cycles to read.*

## Lesson: pointer chasing

`mov rdx, [rdx]` loads the next node's address from the current node. The CPU can't
even *start* the next load until this one returns. When the nodes are scattered over
more memory than the caches hold, every node is a full trip to memory: ~200 cycles each,
with the rest of the machine idle. Out-of-order execution can't help, because there's
nothing independent to do.

## Lesson: memory-level parallelism

The CPU *can* have many misses in flight at once (real cores track 10–20). It just needs
independent addresses. Here there are 8 lists, and they don't depend on each other:
advance all of them by one node per round, and the 8 loads of a round overlap. That's
8 trips for the price of one, the same idea as level 98's accumulators, applied to
memory. Hash-table probes, B-tree lookups and garbage collectors are sped up the same
way ("batching", "interleaving", coroutines that switch on a miss).

**Software prefetch** (`prefetcht0 [addr]`) starts a load that nobody waits for: useful
when you know an address well before you need it (an array of pointers, the next item
in a batch). In a single list you never know it early, which is the whole problem.

## Lesson: the TLB

Every address your program uses is **virtual**: the CPU translates it to a physical
address through page tables, and caches the translations in the **TLB** (the game's
CPU: 64 entries). With 4 KiB pages, 64 entries cover 256 KiB. The 4 MiB pool here is
1024 pages, so random nodes miss the TLB too, and each miss needs a page walk.

**Huge pages** (2 MiB) cover the pool with 2 entries. On Linux, ask with
`madvise(addr, length, MADV_HUGEPAGE)` (syscall 28, advice 14) on 2 MiB-aligned memory.
Try it here and compare the report: the TLB misses vanish, but once eight misses overlap
the time hardly moves, because the walks were hiding behind the memory latency too.
Measure; don't assume.

## Gate

`ring_sum_lists(heads, k)` returns the sum of the values in `k` (1–8) linked lists
(`heads[i]` = the first node, 0 = empty; a node is `dq next, dq value`). The nodes are
scattered over a 4 MiB pool. The starter walks the lists one by one: about 200 cycles
per node. Get it under **45 cycles per node**.
