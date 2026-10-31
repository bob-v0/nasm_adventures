# Level 99 — Measuring

*Arc VII. Correct isn't enough any more: now it has to be fast. Before you can make
anything fast, you have to be able to tell.*

## The game's CPU

Real timings depend on your exact CPU, its temperature, other programs, the virtual
machine you may be in… Two runs never agree, and grading on them would be a lottery.
So in this arc your code runs on **the game's CPU model**: a simplified but honest
modern x86 core, the same for everyone, every time. It's documented at the top of
`ring/perf.py`:

- **out of order**: up to 4 instructions start per cycle, each as soon as its inputs are
  ready (an `imul` takes 3 cycles, an `add` 1, a `div` about 40);
- a **branch predictor** (a wrong guess costs 15 cycles);
- **caches**: L1 32 KiB, L2 1 MiB, memory 200 cycles away, a prefetcher;
- the classic traps: store forwarding, 4K aliasing, denormals, split accesses.

Real CPUs differ in detail, never in kind: what's slow here is slow there. When a test
is too slow, the game's report tells you where the cycles went.

## Lesson: the time-stamp counter

`rdtsc` loads a cycle counter into `edx:eax`. `shl rdx, 32` / `or rax, rdx` makes one
64-bit number of it. So: read it before, read it after, subtract? Not quite. Four things
get in the way.

**1. Out-of-order execution.** `rdtsc` is an instruction like any other. It can run
*before* the instructions above it have finished, or *after* the ones below it have
started, and then you time the wrong thing. Fences pin it in place: `lfence` waits until
everything before it has finished, and `rdtscp` is an `rdtsc` that does the same for the
read itself. The usual pattern:

```
lfence          ; everything before has finished
rdtsc           ; start
lfence          ; nothing after starts early
call fn
rdtscp          ; end: waits for fn to finish
lfence          ; nothing after starts early
```

**2. Warm-up.** The first call pays for cold caches and an untrained branch predictor.
Unless that's what you want to measure, call the function a few times first.

**3. Noise.** Interrupts, other programs and frequency changes only ever *add* time. So
repeat the measurement and keep the **minimum** (or a low percentile; never the
average). Five runs of `512 509 1730 508 509` cycles mean 508: the 1730 is an interrupt,
not your code.

**4. Overhead.** The fences and the `call` cost cycles too. Measure an empty function
exactly the same way, and subtract.

## Gate

`ring_measure(fn)` receives a function (no arguments; it may change the caller-saved
registers) and returns, in `rax`, the cycles one call of it takes: warm, fenced, the
minimum of many runs, minus the cost of measuring. The tests use four functions (a
dependency chain, memory reads, divisions, a small loop) with interrupts arriving at
random. Your answer must be within 10% of a careful measurement.

On a real Linux x86 machine, `perf stat ./program` in the {{terminal}} shows the real
counters (where the container allows it).
