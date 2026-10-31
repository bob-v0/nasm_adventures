# Level 98 — Pipelines

*The CPU can start four instructions a cycle. Your loop gives it one, then makes it
wait for that one to finish.*

## Lesson: latency and throughput

Every instruction has two speeds:

- **latency**: the cycles from when its inputs are ready until its result is: `add` 1,
  `imul` 3, `addsd` 4, `divsd` 14;
- **throughput**: how many can *start* per cycle when they don't depend on each other:
  `add` 4 per cycle, `addsd` 2, `imul` 1.

How can two `addsd` start every cycle when each takes 4? The units are **pipelined**,
like an assembly line: an addition moves one stage further each cycle, and a new one can
enter behind it. A unit with 4 stages can have 4 additions in progress at once, if they
don't need each other's results.

## Lesson: dependency chains

```
.next:  addsd xmm0, [rdi]      ; needs the previous xmm0
```

Each addition needs the sum from the one before, so they form a **chain**: one every 4
cycles, no matter how many units sit idle. That's the starter: about 4.5 cycles per
value, under one instruction per cycle on a machine that can do four.

The fix is to break the chain into **independent** ones. Keep four sums: `xmm0` gets
values 0, 4, 8…, `xmm1` gets 1, 5, 9…, and so on. Add the four together at the end. Now
four additions are in flight at any time.

![One sum versus four: the same additions, one chain or four overlapping chains](chains.svg)

Compilers do this for integers by themselves (`-O2`), and for floats only if you allow
it (`-ffast-math`), because…

## Lesson: floating point isn't associative

`(a + b) + c` and `a + (b + c)` can differ in the last bit, since each addition rounds.
Four accumulators add in a different order, so on real data the result can change
slightly. The tests use small whole numbers, which doubles represent exactly, so every
order gives the same answer.

## Gate

`ring_sum(values, n)` returns the sum of `n` doubles in `xmm0`, for any `n` (including
0 and odd sizes), in under **2 cycles per value** (plus a little for setup) on the game's
CPU. The starter is correct and slow.
