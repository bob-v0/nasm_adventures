# Level 82 — Bug: Ordering Violation ◆◆◆

*A mutual-exclusion algorithm with a correctness proof in every textbook, running on the
most common processor family in the world, letting two threads into the critical
section at once.*

## Symptoms

Peterson's algorithm (1981) gives two threads mutual exclusion with nothing but loads
and stores:

```
lock(me):   flag[me] = 1            ; I want to enter
            turn = other            ; but you go first, if you want to
            while flag[other] and turn == other: wait
unlock(me): flag[me] = 0
```

It's correct, and so is Dekker's algorithm before it, **on a sequentially consistent
machine**. Two threads enter 20 times each, and the program counts the moments when both
were inside. It's usually 0. Not always.

## Background: which reordering

The proof relies on this: when thread 0 reads `flag[1]`, its own `flag[0] = 1` is
already visible to thread 1. On x86 it may still be in thread 0's **store buffer**
(level 83). So both threads store their flag, both read the other's flag as 0 (the
stores haven't drained yet), and both walk in.

That's an **ordering violation**: every access is atomic and the logic is right, but the
*order in which other cores observe* the accesses isn't the program order.

## Background: the minimum fence

Fences cost tens of cycles each, so the craft is to put exactly the ones the algorithm
needs, exactly where it needs them. Ask which **store → load** pairs must stay in order.
Here, the stores to `flag[me]` and `turn` must be visible before the load of
`flag[other]`. That needs one `mfence` (or turning the store to `turn` into an `xchg`)
in `lock`. `unlock` needs nothing, because x86 never reorders a store with earlier
memory operations.

(In C11 the same fix is `atomic_thread_fence(memory_order_seq_cst)`, or making the
accesses `seq_cst` atomics. On ARM or POWER, Peterson needs more fences still, because
more reorderings are allowed there.)

## Gate

1. Add a witness: a schedule under which both threads are inside together:
   `;! witness schedule = N`. (It's rare: try several.)
2. Fix it, changing at most **2 lines**, with at most one fence in `peterson_lock` and
   none in `peterson_unlock`.
