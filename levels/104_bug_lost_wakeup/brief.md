# Level 104 — Bug: Lost Wakeup ◆◆◆

*The consumer went to sleep waiting for a value. The value had already arrived. Nobody
will ever knock again.*

## Symptoms

Level 106's channel got an improvement: when a receiver finds the channel empty, it
first tells the statistics service that it's going idle, then waits. Since that
change, runs sometimes end with the runtime's complaint that tasks are **waiting
forever**, with values sent but never received. Most task orders are fine.

## Background: check-then-wait

Waiting for a condition takes three steps:

1. **check** the condition (is the channel empty?);
2. **register** a waker (put yourself in the receivers' queue);
3. **sleep** (park).

The other side does: change the state (add a value), then wake whoever registered.

If the other side runs **between 1 and 2**, it changes the state, finds nobody to wake,
and moves on. Then you register and sleep, waiting for something that has already
happened. That's a **lost wakeup**. With threads the window is between two
instructions, which is why condition variables take the mutex into `wait()` and why
`while (!cond) wait()` is always a loop. With tasks the window is any **await** between
the check and the sleep, and `note_idle` is one.

The cure is the same everywhere: there must be no gap between the last check and going
to sleep. Re-check the condition after anything that could have let others run, or
register the waker **before** the final check, so a change after it always finds you.

## How the game tests it

As in level 106: producers and consumers, the harness logs every send and receive, and
every test runs under the plain order and many shuffled schedules. A task stuck
forever, a lost value or a broken order fails the test, and the report names the
schedule.

## Gate

1. Add a witness: a schedule under which the **original** loses a wakeup:
   `;! witness schedule = N`.
2. Fix the channel, changing at most **6 lines**.
