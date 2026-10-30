# Level 87 — Locks

*Atomics protect one word. Real data structures need a whole region of code to run
without interference: a lock.*

## Lesson: spinlocks

The simplest lock is a word: 0 free, 1 taken. To lock, `xchg` a 1 into it: if the old
value was 0, you own the lock; otherwise loop until it looks free, then try again.
Unlock: store 0. While looping, `pause` tells the CPU you're spinning, which saves power
and is kinder to a hyper-threaded sibling.

Spinlocks are great when critical sections are tiny and every thread has its own core.
They're terrible when the holder **isn't running**: preempted by the scheduler, or
waiting for a page fault. Every waiter then burns its whole time slice, often making it
*less* likely that the holder gets to run. The starter is a spinlock.

## Lesson: futex

A **futex** lets a waiter sleep in the kernel and be woken by the unlocker. The trick
that makes it fast: the kernel is involved **only when there's contention**.
`futex(addr, FUTEX_WAIT, val)` sleeps only if `*addr` still equals `val` (checked
atomically with going to sleep, so a wake can't slip in between: compare level 104).
`futex(addr, FUTEX_WAKE, n)` wakes up to `n` sleepers.

## Lesson: the three-state mutex

Unlock needs to know whether anyone might be asleep, or it would make a syscall every
time. Ulrich Drepper's mutex ("Futexes Are Tricky", 2004) uses three states:
**0** free, **1** locked, **2** locked and maybe someone sleeping.

```
lock:    cmpxchg 0 -> 1            ; free? taken, no syscall
         loop: old = xchg(m, 2)    ; announce a waiter (and grab it if it was free)
               if old == 0: done
               futex_wait(m, 2)
unlock:  old = fetch_add(m, -1)    ; 1 -> 0: nobody was waiting
         if old != 1: m = 0; futex_wake(m, 1)
```

glibc's `pthread_mutex_t` works like this, with more care for fairness and priority
inheritance.

## Gate

Write `mutex_lock(m)` and `mutex_unlock(m)` (`m` points to a zeroed dword). The game's
harness runs 4 threads doing 25 slow, non-atomic updates each under your lock. The
total must come out right under every schedule, waiting threads must sleep (the
whole run must take under 18 000 instructions), and with no contention, no futex calls.
