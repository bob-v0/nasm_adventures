# Level 97 — Branch Prediction

*The same code, the same data, sorted or not: 6× faster sorted. The CPU isn't reading
the data. It's guessing.*

## Lesson: the front end guesses

The CPU fetches and decodes instructions long before it executes them: dozens of
instructions ahead, in the out-of-order window. At a conditional branch it can't wait
to find out which way to go, so the **branch predictor** guesses from the branch's
history, and execution continues down the guessed path **speculatively**. If the guess
was wrong, all that work is thrown away and fetching restarts at the right place: about
**15 cycles** lost (more on real CPUs with deeper pipelines).

Predictors are very good at patterns: loop branches (taken, taken, …, not taken),
branches that always go the same way, short repeating patterns, branches correlated
with earlier ones. They can't predict **random** data. Sorted data turns
`if (x >= 128)` into a long run of "no" followed by a long run of "yes": nearly perfect.
Random data: right half the time.

(Speculation leaves traces in the caches even when it's thrown away. That's the Spectre
family of attacks: see Arc X.)

## Lesson: don't branch, compute

When a branch only chooses between two values, compute both and **select** without a
branch:

- `cmovcc dst, src`: copies src into dst if the condition holds, otherwise does nothing.
  No guess is involved: it just waits for the flags.
- `setcc r8` gives 0 or 1. `neg` turns that into 0 or all ones, a **mask** you can `and`
  with.
- `adc`, `sbb`, `min`/`max` instructions in SIMD (Arc IX)…

Branchless code always pays for both sides, so it wins only when the branch is
unpredictable. Compilers often make this choice for you, sometimes wrongly.

## Gate

`ring_sum_big(bytes, n)` adds up the bytes that are ≥ 128 (unsigned). The starter is
fast on sorted data and very slow on random data. Make random data take under **3
cycles per byte** (plus a fixed allowance for the first, cold cache misses) on the game's
CPU.
