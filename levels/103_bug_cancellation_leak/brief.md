# Level 103 — Bug: Cancellation Leak ◆◆◆

*A client hangs up, a timeout fires, a user presses Cancel: the work in progress must
stop. With tasks, it stops at an await, in the middle of whatever the task was doing,
holding whatever it was holding.*

## Symptoms

Workers save records to a small database. Each takes a buffer from the allocator,
formats its record, takes the database lock, waits for the slow disk, appends the
record, and releases the lock and the buffer. A supervisor can **cancel** a worker. The
workers handle it the obvious way: if an await says "cancelled", return. Since then the
service sometimes freezes, with tasks waiting forever, and memory leaks.

## Background: cancellation in async code

In the game's runtime (as in Rust's dropped futures, Python's `CancelledError` or C#'s
cancellation tokens) cancellation is delivered **at an await point**. `rt_cancel(task)`
makes the task's current or next await return **−125 (`ECANCELED`)**. The task must
then unwind: stop its work and **release everything it holds**, on every path.

What it holds depends on **where** it was cancelled:

| cancelled at… | holds |
|---|---|
| `rt_lock` (still waiting) | the buffer, but **not** the lock: `rt_lock` returned without taking it |
| `rt_sleep` (inside the critical section) | the buffer **and** the lock |

Forget the buffer and memory leaks, slowly. Forget the lock and every other task that
needs it waits forever: the whole service freezes. Release a lock you **don't** hold and
you break someone else's critical section. Languages give this structure names (RAII,
`defer`, `try/finally`, `with`); in assembly it's labels: one cleanup path per set of
held resources, in reverse order of acquisition.

## How the game tests it

One run without cancellation, then one run per await point of that run, cancelling
the task that reaches it, right there. Every time: no task stuck forever, every buffer
freed (the game's checked allocator knows), every job either done or cancelled, and
exactly one record per finished job. The report says which task was cancelled at which
of its awaits.

## Gate

Make every way out of `worker` release exactly what it holds, changing at most **8
lines**.
