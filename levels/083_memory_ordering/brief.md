# Level 83 — Memory Ordering

*Thread A writes x, then reads y. Thread B writes y, then reads x. Can both read the old
values? Every programmer's intuition says no. Every x86 CPU says yes.*

## Lesson: sequential consistency

The intuitive model of threads is **sequential consistency** (SC): the operations of all
threads are interleaved in some order, and every load sees the latest store before it in
that order. Under SC, in the test below, one of the two stores comes first, so at least
one load sees a 1:

```
left:   x = 1          right:  y = 1
        r1 = y                 r2 = x           ; r1 = r2 = 0?  never, under SC
```

## Lesson: x86-TSO

Real cores don't wait for each store to reach the cache. They put it in a **store
buffer** and carry on. The core's own later loads see the buffered value (store
forwarding), but **other cores don't, until it drains**. So `left` can read `y` while its
`x = 1` is still sitting in its buffer, and `right` does the same: both read 0.

x86's memory model is called **TSO** (total store order). Everything else stays in
order:

| reordering | allowed on x86? |
|---|---|
| a load with a later load | no |
| a store with a later store | no |
| a load with a later store | no |
| **a store with a later load** (to another address) | **yes** |

ARM and POWER allow much more, which is why portable code uses the C11/C++11 atomics
with explicit orderings. The game's threads now run on a TSO model: each thread has a
store buffer that drains at moments the schedule chooses.

## Lesson: fences

`mfence` waits until the store buffer has drained before any later load or store goes
ahead. Any `lock`-prefixed instruction, and `xchg` with memory, do the same. That's why
C's `atomic_store` with `memory_order_seq_cst` compiles to `xchg` on x86, and why
`lock`ed instructions cost what they cost.

## Gate

1. `sb_left` / `sb_right`: the test above, exactly. Find a schedule under which both
   threads read 0, and write it down: `;! witness schedule = N`.
2. `fenced_left` / `fenced_right`: the same with fences, so that `r1 = r2 = 0` can never
   happen. The tests try many schedules.

(On a real multi-core x86 you can see it too: run the two sides in a loop many
thousands of times; a few percent of rounds end with both zeros.)
