# Level 84 — Bug: Livelock & Starvation ◆◆◆

*The lock is correct: never two holders. No deadlock either: someone always makes
progress. It's just never you.*

## Symptoms

Four threads share a test-and-set spinlock (level 87's starter), 15 short critical
sections each. Everything is logged: "I want the lock", "I got it". Some threads wait
while the others get in ten, twenty times in a row.

## Background: progress guarantees

"Correct" for a lock means several things:

- **mutual exclusion**: never two holders;
- **deadlock freedom**: if threads want the lock, *someone* gets it;
- **starvation freedom** (**bounded waiting**): if *you* want it, you get it, after at
  most N others.

A test-and-set lock gives the first two, not the third. Nothing in it remembers who
asked first: whoever happens to `xchg` at the right moment wins. The thread that just
unlocked is running, so its next `xchg` is right there, while waiters only notice the
lock is free when they next look (a cache-line round trip later, on real hardware). On
real machines the fastest core, or the one sharing a cache with the holder, wins again
and again.

## Background: ticket locks

A **ticket lock** works like a deli counter: two counters, `next_ticket` and
`now_serving`.

```
lock:    my = fetch_add(next_ticket, 1)      ; take a number
         while now_serving != my: pause      ; wait for it to come up
unlock:  now_serving += 1                    ; next, please
```

Strictly first come, first served. The Linux kernel used ticket spinlocks for years.
They're fair, but every waiter watches the same `now_serving` line, so each unlock
makes it bounce between all their caches (queue locks like MCS fix that: one cache line
per waiter).

## Background: livelock

A relative of deadlock: threads that are all *active*, and all get nowhere. Two people
in a corridor who keep stepping aside the same way; two threads that each `trylock`
the second lock, fail, release the first and retry in lockstep forever. The usual cure
is randomized back-off.

## How the game tests it

From the log, the game counts, for every wait, how many times other threads got the
lock while this one was waiting. A fair lock allows 3 (one per other thread); the game
allows 5, because a thread logs "I want it" a few instructions before it actually asks.

## Gate

1. Add a witness: a schedule where a thread is overtaken more than 5 times:
   `;! witness schedule = N`.
2. Make the lock fair (`acquire` / `release`), changing at most **14 lines**.
