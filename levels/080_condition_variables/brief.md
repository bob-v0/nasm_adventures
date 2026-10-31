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
after the unlock, `cond` has changed and `futex_wait` returns at once, so nothing is
lost:

```
waiter                                 signaller
seq = cond               ; 7
unlock(mutex)
                                       lock(mutex); put an item
                                       cond += 1 (now 8); futex_wake: nobody asleep yet
futex_wait(&cond, 7)     ; cond is 8, not 7: returns at once
lock(mutex)              ; and finds the item
```

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
item. And POSIX allows **spurious wakeups** (a wait that returns with no signal) anyway.
Writing `if` instead of `while` is one of the most common concurrency bugs there is.

## Gate

Write a bounded blocking queue:

| function | does |
|---|---|
| `queue_init(q, cap)` | `q`: 4096 zeroed bytes for your struct; `cap`: 1–64 |
| `queue_put(q, value)` | adds a value; sleeps while the queue is full |
| `queue_get(q)` | `rax` = the oldest value, `rdx` = 1; sleeps while empty; once closed and empty, `rdx` = 0 |
| `queue_close(q)` | no more puts; wakes every sleeping getter |

The harness provides `mutex_lock` / `mutex_unlock` (level 87's) and runs producer and
consumer threads under many schedules. Every value must arrive exactly once, each
producer's in order; producers really wait at capacity; nothing is stuck; nobody spins.
