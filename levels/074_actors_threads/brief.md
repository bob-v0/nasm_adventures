# Level 74 — Actors Across Threads

*Arc VI's actors ran on one thread. Real runtimes (Erlang's BEAM, Akka, Orleans, Tokio's
tasks) run thousands of actors on a handful of worker threads, one per core. Here's the
core of one.*

## Lesson: the shape of the runtime

- Each actor has a **mailbox**. Anyone can send to it, from any thread: it's a
  **multi-producer, single-consumer** (MPSC) queue.
- An actor with messages is **scheduled**: put on a run queue that worker threads take
  from (the game provides the run queue and the workers).
- A worker **runs** the actor: it hands it its messages one by one, oldest first.
- The actor model's promise: an actor processes **one message at a time**. So it must
  never run on two workers at once, and then its state needs no locks.

## Lesson: an MPSC mailbox

Senders push onto a lock-free stack (level 77). The single consumer doesn't pop one by
one: it takes **the whole stack at once** with `xchg [mailbox], 0` (nobody else ever
removes, so there's no ABA), then reverses the list to get the oldest first:

```
three sends:     mailbox ──▶ m3 ──▶ m2 ──▶ m1 ──▶ 0     newest first
take them all:   xchg [mailbox], 0                       mailbox is empty again
reverse:         m1 ──▶ m2 ──▶ m3 ──▶ 0                  oldest first
```

Messages from one sender stay in order: each sender's pushes happen one after the other,
and the reversal keeps that order.

## Lesson: scheduling exactly once

A **scheduled** flag means "queued or running". A sender does `xchg flag, 1`, and only
the one that sees 0 calls `runq_push`. The runner processes batches until the mailbox is
empty, then **goes idle**. That's the delicate part:

```
flag = 0
if mailbox is not empty:            ; a sender may have pushed after my last batch, but
    if xchg(flag, 1) == 0:          ; seen the flag still at 1 and not scheduled me
        process again               ; (if it returns 1, a sender already rescheduled me)
```

Clearing the flag and then reading the mailbox is a store followed by a load: on x86
they can be reordered (level 83), and then a message can be stranded with nobody
scheduled to read it. Put a fence there. That reordering is rare enough that the tests
here may not catch it, but real machines will.

## Gate

Write `actor_send` and `actor_run`:

| function | does |
|---|---|
| `actor_send(actor, msg)` | from any thread, any time: put `msg` in the actor's mailbox; if the actor isn't scheduled yet, schedule it with `runq_push(actor)` |
| `actor_run(actor)` | called by a worker: hand the actor's messages, oldest first, to `behavior(actor, msg)`, then return |

An actor is 128 zeroed bytes: `+0` and `+8` are yours (the harness uses `+64` onwards).
A message is `dq next, dq value`, and `behavior` frees it. The harness runs 3 workers
and 3 producer threads sending 60 messages to 4 actors, under many schedules. Every
message must be processed exactly once and freed, each sender's messages in order, and
no actor may ever run on two workers at the same time.
