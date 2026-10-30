# Level 80 — Condition Variables

*A lock says "one at a time". A queue also needs "wait until there's something to take",
and "wait until there's room". That's a condition variable.*

## Lesson: waiting for a condition

A consumer that finds the queue empty must wait, but **not** while holding the mutex,
or no producer could ever add anything. And it must not miss the moment a producer adds
something between "I saw it empty" and "I'm asleep" (level 104's lost wakeup, now with
real threads). A **condition variable** packages exactly that:

```
cond_wait(cond, mutex):   atomically: release the mutex and sleep on cond
                          when woken: take the mutex again
cond_signal(cond):        wake one sleeper        (broadcast: wake them all)
```

## Lesson: a condition variable from a futex

A condition variable can be a single counter:

```
wait(cond, mutex):  seq = cond         ; read BEFORE unlocking
                    unlock(mutex)
                    futex_wait(&cond, seq)
                    lock(mutex)
signal(cond):       atomic cond += 1
                    futex_wake(&cond, 1)
```

The futex compares `cond` with `seq` atomically with going to sleep. If a signal arrived
after the unlock, `cond` has changed and `futex_wait` returns at once: nothing is lost.
(glibc's real implementation is far more intricate, to be fair to waiters and to support
broadcasts efficiently, but this is the core.)

## Lesson: the predicate loop

**Always** wait in a loop that re-checks the condition with the mutex held:

```
lock
while queue is empty: wait(not_empty, mutex)
take an item
signal(not_full)
unlock
```

Between the signal and your getting the mutex back, another consumer may have taken the
item. And POSIX allows **spurious wakeups** anyway. `if` instead of `while` is one of the
most common concurrency bugs there is.

## Gate

Write a bounded blocking queue: `queue_init`, `queue_put` (sleeps while full),
`queue_get` (sleeps while empty; reports "closed" once closed and empty) and
`queue_close` (wakes every sleeping getter). The harness provides `mutex_lock` /
`mutex_unlock` and runs producer and consumer threads under many schedules. Every value
must arrive exactly once, each producer's in order; producers really wait at capacity;
nothing is stuck; nobody spins.
