# Level 106 — Channels

*Tasks that share memory step on each other. Tasks that pass messages through a
queue don't have to know about each other at all. Go, Rust and Kotlin call it a
channel.*

## The game's task runtime

From here on the game links in its own task runtime, your level 107 runtime grown up
(`ring/runtime/rt.asm`, read it any time):

| call | does |
|---|---|
| `rt_spawn(fn, arg)` | a new ready task running `fn(arg)` |
| `rt_current()` | the running task |
| `rt_yield()` | let other ready tasks run first |
| `rt_park()` | suspend until someone calls `rt_unpark(this task)` |
| `rt_unpark(task)` | make a parked task ready (no effect on a task that isn't parked) |
| `rt_sleep(ms)`, `rt_await_readable(fd)`, `rt_lock(m)` / `rt_unlock(m)`, `rt_cancel(task)` | later levels |

A *task* is a function running on its own stack that the runtime can suspend and
resume (level 107). Each call that can suspend is an **await point**: other tasks may run
before it returns. When several tasks are ready, **the game picks which runs next**. The tests
try many different orders (*schedules*), so code that only works in one order fails.

## Lesson: a bounded channel

A **channel** is a queue between tasks with a **capacity**: a *ring buffer* of `cap`
slots (an array whose end wraps around to its start), plus `head` (the index of the
oldest value) and `count`:

```
cap = 4, head = 1, count = 2

slot:      0      1      2      3
        [    ] [ 10 ] [ 11 ] [    ]
                  ↑ head: recv takes 10 next
                                  ↑ send puts the next value at (head + count) % cap = 3
```

When it's **full**, `send` waits. That's **backpressure**: a fast producer is slowed to
the speed of its consumers instead of filling memory. When it's **empty**, `recv` waits.

## Lesson: wakers

"Wait" doesn't mean `rt_yield` in a loop. That **spins**: the task gets run again and
again only to find nothing has changed. Instead the waiting task leaves a **waker** (a
note saying "wake me", here its task pointer in a queue in the channel) and **parks**.
Whoever changes the channel so that a waiter could proceed takes the first waker and
unparks that task: `send` wakes a receiver, `recv` wakes a sender, `close` wakes all
receivers.

Two rules make this correct:

1. **Nothing may await between "check the condition" and "park".** Otherwise the
   wakeup can happen in between, and the task parks for a wakeup that already happened.
   (That's a famous bug, two levels from now.)
2. **After waking, check again**, in a loop. Being woken means "something changed", not
   "it's your turn": another task may have taken the slot first.

## Gate

Write `chan_init`, `chan_send`, `chan_recv` and `chan_close` (see the starter for the
exact contract). The game's harness runs producers and consumers through your channel
and logs every send and receive. Under every schedule it tries:

- every value arrives exactly once, and each producer's values in order;
- senders really wait: at most `cap` values (plus one per consumer, on its way out) are
  ever sent but not yet received;
- no task is left waiting forever, and nobody spins.

Constraint: at most 110 instructions.
