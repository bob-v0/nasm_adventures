# Level 11 — Scheduler

*Most of the time, most tasks are waiting for something. A good scheduler spends no
time on them at all.*

## The task

Level 12's tasks were always ready to run. Real ones wait: for time to pass, for input,
for each other. Add three things to level 12's kernel:

| | |
|---|---|
| **nanosleep** (35) | `nanosleep(&{seconds, nanoseconds})`: sleep at least that long, using no CPU |
| **setpriority** (141) | `setpriority(0, 0, nice)`: the caller's nice, −20 to 19 (clamped). Lower runs first |
| **idling** | when every task is asleep, wait for the timer with `hlt` |

The timer now ticks at **HZ = 100**, calibrated against the PIT as in level 33, and counts
in `[ticks]`. The tests: sleepers must wake in the order of their sleep times. A
high-priority task runs before a low one whenever both are ready. And a busy task that
never yields can't keep a sleeper asleep.

## Lesson: blocking

A sleeping task isn't *ready*. It gets a state of its own (3) and a wake-up tick, and
`schedule` skips it. On every tick the timer handler wakes the sleepers whose time has
come. A sleep is rounded *up* to whole ticks, plus one, because the current tick is
already partly over, and a sleep may be longer than asked, never shorter.

## Lesson: the idle loop

When nobody is ready, there's still a CPU executing instructions. It mustn't spin
(that wastes power, and on a real machine heat). It waits:

```
.idle:
    sti                 ; let the timer in...
    hlt                 ; ...and stop until it comes
    cli
    jmp .look_again
```

The timer interrupts the `hlt` in ring 0, wakes whoever is due, and returns into the
loop. (The handler notices it came from ring 0 and doesn't schedule from there.)

## Lesson: priorities

The simplest priority scheduler: always run the ready task with the best priority. Among
equals, take turns, starting after the current one. A low-priority task only runs when
everything better is asleep or done, which is exactly what `nice` promises.

## Gate

Sleepers wake in order, priorities are kept, nobody's sleep is stretched by a busy
neighbour.
