# Level 87 — Locks

*Atomics protect one word. Real data structures need a whole region of code to run
without interference: a lock.*

## Lesson: spinlocks

The simplest lock is a word: 0 free, 1 taken. To lock, `xchg` a 1 into it. If the old
value was 0, you own the lock; otherwise loop until it looks free, then try again. To
unlock, store 0. While looping, `pause` tells the CPU you're spinning, which saves power
and is kinder to a hyper-threaded sibling.

Spinlocks are great when critical sections are tiny and every thread has its own core.
They're terrible when the holder **isn't running**: preempted by the scheduler, or
waiting for a page fault. Then every waiter burns its whole time slice, often making it
*less* likely that the holder gets to run. The starter is a spinlock.

## Lesson: futex

A **futex** lets a waiter sleep in the kernel and be woken by the unlocker. What makes
it fast is that the kernel is involved **only when there's contention**.
`futex(addr, FUTEX_WAIT, val)` sleeps only if `*addr` still equals `val`, checked
atomically with going to sleep, so a wake can't slip in between (compare level 104).
`futex(addr, FUTEX_WAKE, n)` wakes up to `n` sleepers.

## Lesson: the three-state mutex

Unlock needs to know whether anyone might be asleep; otherwise it would have to make a
syscall every time. Ulrich Drepper's mutex ("Futexes Are Tricky", 2004) gives the word
three states: **0** free, **1** locked, **2** locked and maybe someone sleeping.

```
lock:    cmpxchg 0 -> 1            ; free? taken, no syscall
         loop: old = xchg(m, 2)    ; announce a waiter (and grab it if it was free)
               if old == 0: done
               futex_wait(m, 2)
unlock:  old = fetch_add(m, -1)    ; 1 -> 0: nobody was waiting
         if old != 1: m = 0; futex_wake(m, 1)
```

How the word moves between its states:

| from | what happens | to |
|---|---|---|
| 0 | `lock` with no contention: `cmpxchg` 0 → 1 succeeds, no syscall | 1 |
| 1 | another thread's `lock`: `xchg` puts 2 in, then it sleeps on the futex | 2 |
| 1 | `unlock`: `fetch_add` −1 finds 1, so nobody waits: no syscall | 0 |
| 2 | `unlock`: finds 2, stores 0 and wakes one sleeper | 0 |
| 0 | the woken thread's `xchg` puts 2 in and finds 0: the lock is its | 2 |

That last row takes the lock in state 2, not 1: the thread can't know whether others
are still asleep, so it plays safe. The cost is at most one unnecessary wake.

glibc's `pthread_mutex_t` works like this, with more care for fairness and priority
inheritance.

## Gate

Write `mutex_lock(m)` and `mutex_unlock(m)` (`m` points to a zeroed dword). The game's
harness runs 4 threads doing 25 slow, non-atomic updates each under your lock. The
total must come out right under every schedule, waiting threads must sleep (the
whole run must take under 18 000 instructions), and with no contention, no futex calls.
