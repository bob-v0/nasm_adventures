# Level 79 — Bug: Lost Wakeup II ◆◆◆

*It passed review, it passed the tests, it ran in production for months. Then one
night, every thread in the service was asleep, waiting for each other.*

## Symptoms

Level 80's blocking queue, from a codebase where `cond_wait` was "simplified": it
releases the mutex first, then reads the condition's counter and sleeps on it. Almost
every run is fine. Very rarely the program stops for good. The game reports every
thread asleep on a futex: consumers on `not_empty` with producers waiting, or producers
on `not_full` with nobody left to take anything.

## Background: the window

A sleeping wait has three steps: release the mutex, decide what you're waiting for,
sleep. Here's what goes wrong if "decide" comes after "release":

```
waiter                                  signaller
unlock(mutex)
                                        lock(mutex); change the queue
                                        cond += 1; futex_wake(cond)   ; nobody asleep yet
seq = cond          ; already the NEW value
futex_wait(cond, seq)                   ; equal: sleeps, for a signal already sent
```

Level 104 had the same bug with tasks. With threads the window is a few instructions
wide, which is why it's so rare: the signaller must run its whole critical section in the
moment between two instructions of the waiter. On a busy machine that happens, a few
times a day.

The futex was designed against exactly this: `futex_wait(addr, expected)` sleeps only if
`*addr == expected`, checked atomically with going to sleep. But that only helps if
`expected` was read **while the condition was still protected by the mutex**: read the
counter before unlocking, and any signal after the unlock changes it.

## Background: finding rare bugs

Running the program a million times hoping to hit the window doesn't work, and on a
real machine it can't be replayed when it does. The game's scheduler explores
interleavings on purpose. Most schedules give threads short turns, and sometimes one gets
a long uninterrupted run, which is what this bug needs. Each schedule is numbered, so a
failure can be replayed exactly. (Real tools: PCT, CHESS, rr's chaos mode.)

## Gate

1. Add a witness: a schedule under which the original loses a wakeup:
   `;! witness schedule = N`. (A handful in every hundred.)
2. Fix it, changing at most **2 lines**.
