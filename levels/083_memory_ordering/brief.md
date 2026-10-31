# Level 83 — Memory Ordering

*Thread A writes x, then reads y. Thread B writes y, then reads x. Can both read the old
values? Every programmer's intuition says no. Every x86 CPU says yes.*

## Lesson: sequential consistency

The intuitive model of threads is **sequential consistency** (SC): the operations of
all threads are interleaved in some single order, and every load sees the latest store
before it in that order. Take this test, with `x` and `y` both 0 at the start:

```
left:   x = 1          right:  y = 1
        r1 = y                 r2 = x           ; r1 = r2 = 0?  never, under SC
```

Under SC, one of the two stores comes first in the order, before both loads. So at
least one load sees a 1.

## Lesson: x86-TSO

Real cores don't wait for each store to reach the cache. They put it in a **store
buffer**, a short queue of pending stores, and carry on. The core's own later loads
see the buffered value (that's store forwarding), but **other cores don't, until it
drains** to the cache. So `left` can read `y` while its `x = 1` is still sitting in its
buffer, and `right` can do the same: both read 0.

![Each core's store waits in its own store buffer while its load reads the old value from memory](store_buffer.svg)

x86's memory model is called **TSO** (total store order). Apart from this one case,
everything stays in order:

| reordering | allowed on x86? |
|---|---|
| a load with a later load | no |
| a store with a later store | no |
| a load with a later store | no |
| **a store with a later load** (to another address) | **yes** |

ARM and POWER allow much more, which is why portable code uses the C11/C++11 atomics
with explicit orderings. From now on the game's threads run on a TSO model: each thread
has a store buffer that drains at moments the schedule chooses.

## Lesson: fences

`mfence` waits until the store buffer has drained before any later load or store goes
ahead. Any `lock`-prefixed instruction, and `xchg` with memory, do the same. That's why
C's `atomic_store` with `memory_order_seq_cst` compiles to `xchg` on x86, and why
`lock`ed instructions cost what they cost.

## Gate

`x`, `y`, `r1` and `r2` are dwords, all 0 at the start.

1. `sb_left` / `sb_right`: the test above, exactly. Find a schedule under which both
   threads read 0, and write it down: `;! witness schedule = N`.
2. `fenced_left` / `fenced_right`: the same with fences, so that `r1 = r2 = 0` can never
   happen. The tests try many schedules.

(On a real multi-core x86 you can see it too: run the two sides in a loop many
thousands of times; a few percent of rounds end with both zeros.)
