# Level 97 — Branch Prediction

*The same code, the same data, sorted or not: 6× faster sorted. The CPU isn't reading
the data. It's guessing.*

## Lesson: the front end guesses

The CPU fetches and decodes instructions long before it executes them, dozens of
instructions ahead, to keep its out-of-order window full. At a conditional branch it
can't wait to find out which way to go. So the **branch predictor** guesses from the
branch's history, and execution carries on down the guessed path **speculatively**. If
the guess was wrong, all that work is thrown away and fetching restarts at the right
place: about **15 cycles** lost (more on real CPUs with deeper pipelines).

Predictors are very good at patterns: loop branches (taken, taken, …, not taken),
branches that always go the same way, short repeating patterns, branches that follow
earlier ones. What they can't predict is **random** data. Here is the starter's
`jb .skip` (taken = the byte is below 128) on the same bytes, sorted and not:

```
sorted:  T T T T T T T T T T T T T T T T . . . . . . . . . . . . . . . .
random:  T . . T . T T . . . T . T T . T . . T . . T T . T . . . T . T .
```

Sorted, the predictor is wrong about once, where the run changes. Random, it's right
about half the time, and each wrong guess costs 15 cycles.

(Speculation leaves traces in the caches even when it's thrown away. That's the Spectre
family of attacks: see Arc X.)

## Lesson: don't branch, compute

When a branch only chooses between two values, compute both and **select** one without
a branch:

- `cmovcc dst, src` copies `src` into `dst` if the condition holds, and otherwise does
  nothing. No guess is involved: it simply waits for the flags.
- `setcc r8` gives 0 or 1. `neg` turns that into 0 or all ones, a **mask** you can `and`
  with.
- `adc`, `sbb`, and the SIMD `min`/`max` instructions (Arc IX)…

Branchless code always pays for both sides, so it wins only when the branch is
unpredictable. Compilers often make this choice for you, sometimes wrongly.

## Gate

`ring_sum_big(bytes, n)` adds up the bytes that are ≥ 128 (unsigned). The starter is
fast on sorted data and very slow on random data. Make random data take under **3
cycles per byte** (plus a fixed allowance for the first, cold cache misses) on the game's
CPU.
