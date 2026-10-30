# Level 117 — Time

*What time is it? How long did that take? Wait until it's time.*

## Lesson: clocks

`clock_gettime(clock, &ts)` (228) fills a **timespec**: two qwords, seconds and
nanoseconds.

| clock | meaning | use it for |
|---|---|---|
| `CLOCK_REALTIME` (0) | wall-clock time since 1970 | timestamps for humans; can jump (NTP, the user) |
| `CLOCK_MONOTONIC` (1) | time since boot; never goes backwards | measuring durations and deadlines |

Measuring with the wall clock is a classic bug: when the clock is adjusted, durations come
out negative or huge.

`nanosleep(&req, &rem)` (35) sleeps for a timespec. Sleeping is not precise (the kernel
wakes you *at least* that late), so robust code sleeps **until a deadline** it computed
from the monotonic clock, rather than for a fixed time.

On real Linux, `clock_gettime` is so frequent that the kernel maps a small library into
every process, the **vDSO**, so it runs without entering the kernel at all. (Its address
is in the auxiliary vector, `AT_SYSINFO_EHDR`.)

The game's kernel has a deterministic clock: each `clock_gettime` advances it by 1 µs, and
`nanosleep` advances it by exactly the requested time.

## Gate

1. Measure a `nanosleep` of 1.25 s with `CLOCK_MONOTONIC` and print `slept N ms` (whole
   milliseconds, rounded down: `slept 1250 ms`).
2. Then copy stdin to stdout line by line, **rate-limited**: each line must be written at
   least 400 ms after the previous one, but no later than needed (the tests allow 5 ms of
   slack). Write each line with a single `write`.

Constraint: at most 120 instructions.
