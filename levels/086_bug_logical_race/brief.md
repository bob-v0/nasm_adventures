# Level 86 — Bug: Logical Race ◆◆◆

*No data races. Every load and store is atomic, every update locked. The program is
still wrong, because correctness was never about single accesses.*

## Symptoms

Two parts of a service misbehave:

- A **rate limiter** admits at most 10 requests. Four threads try six each. It checks
  `admitted < 10`, validates the request, then does `lock inc [admitted]`. Sometimes
  13 get in.
- Accounts `a` and `b` hold 1000 between them. Two threads move money back and forth
  with `lock sub` / `lock add`; an auditor keeps checking `a + b == 1000`. Sometimes
  the audit fails.

## Background: logical races

A **logical race** (also called a race condition, or an atomicity violation) is a bug
where each step is atomic, but a **sequence** of steps needs to be, and isn't. Two
shapes appear everywhere.

**Check-then-act**: "if there's room, take a slot". Between the check and the act, other
threads check too, and they all see room:

```
count   thread A               thread B
  9     check: 9 < 10, room
  9                            check: 9 < 10, room
 10     take a slot
 11                            take a slot        ; 11 > 10
```

File systems (level 116's TOCTOU), caches ("if not cached, compute and insert"),
singletons and rate limiters all have this bug.

**Multi-variable invariants**: `a + b == 1000` is a fact about two words. No single
atomic instruction updates both, so between the two updates the invariant is false, and
anyone who looks at that moment sees it false.

Data-race detectors don't find these: there's no data race. You have to know the
invariant.

## Background: fixes

- **Make the check part of the act**: `lock xadd` claims a slot and tells you, in the
  same step, whether it was a real one; if not, give it back. Or a `cmpxchg` loop that
  only increments from a value below the limit.
- **A critical section around the whole invariant**: every code path that changes `a`
  and `b`, *and every path that reads both*, holds the same lock.

## Gate

1. Add a witness: a schedule under which the original prints wrong numbers:
   `;! witness schedule = N`.
2. Fix both parts, changing at most **16 lines**. `spin_lock` / `spin_unlock` and a lock
   word, `bank`, are already in the program.
