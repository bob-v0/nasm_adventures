# Level 88 — Bug: Torn Read ◆◆

*Every write publishes a consistent pair. Every read checks the pair. And readers still
see pairs that were never written.*

## Symptoms

A shared 16-byte record `{ count, check }` always satisfies `check = 3·count + 1`: the
writer thread only ever stores consistent pairs. Two reader threads take snapshots and
count the inconsistent ones. There shouldn't be any. There are.

## Background: what's atomic on its own

x86 guarantees that an **aligned** load or store of **up to 8 bytes** happens as one
indivisible access. Anything bigger, or anything that crosses a cache line, can be seen
half-done by another core. A 16-byte record written with two `mov`s is two accesses,
and so is a snapshot made with two loads. Between the two halves, the other side can
complete an entire update. The reader gets the new `count` with the old `check`: a
**torn read**. (Aligned 16-byte SSE accesses are atomic on recent CPUs with AVX, as
Intel and AMD documented in 2021, but older ones gave no such promise, and the game's
model doesn't either.)

The same thing tears 64-bit values on 32-bit machines, timestamps made of seconds +
nanoseconds, a pointer plus its length, or a price plus its currency.

## Background: cmpxchg16b

`lock cmpxchg16b [m]` (with `m` 16-byte aligned) is a compare-and-swap on 16 bytes:
if the memory equals `rdx:rax` it stores `rcx:rbx` and sets ZF; otherwise it loads the
memory into `rdx:rax` and clears ZF. Both cases are **one** atomic access, so it serves as:

- an atomic **16-byte write**: loop until it succeeds;
- an atomic **16-byte read**: compare against anything (say 0:0). On a mismatch you
  get the whole current value; on a match it writes back the same value, which is
  harmless.

Other approaches: a lock around both halves, or a **seqlock** (a version counter the
reader checks before and after reading; the Linux kernel's clock works like that).

## Gate

1. Add a witness: a schedule under which the original counts a torn snapshot:
   `;! witness schedule = N`.
2. Fix it, changing at most **14 lines**: every update and every snapshot must be one
   indivisible 16-byte access.
