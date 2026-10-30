# Level 74 — Actors Across Threads

*Arc VI's actors ran on one thread. Real runtimes (Erlang's BEAM, Akka, Orleans, Tokio's
tasks) run thousands of actors on a handful of worker threads, one per core. Here's the
core of one.*

## Lesson: the shape of the runtime

- Each actor has a **mailbox**. Anyone can send to it, from any thread: it's a
  **multi-producer, single-consumer** (MPSC) queue.
- An actor with messages is **scheduled**: put on a run queue that worker threads take
  from (the game provides the run queue and the workers).
- A worker **runs** the actor: hands it its messages one by one, oldest first.
- The actor model's promise: an actor processes **one message at a time**. So it must
  never run on two workers at once, and then its state needs no locks.

## Lesson: an MPSC mailbox

Senders push onto a lock-free stack (level 77). The single consumer doesn't pop one by
one: it takes **the whole stack at once** with `xchg [mailbox], 0` (nobody else ever
removes, so there's no ABA), then reverses the list to get the oldest first. Messages
from one sender stay in order: every sender's pushes are ordered, and the batch reversal
keeps them so.

## Lesson: scheduling exactly once

A **scheduled** flag says "queued or running". A sender does `xchg flag, 1`: only the one
that sees 0 calls `runq_push`. The runner processes batches until the mailbox is empty,
then **goes idle**, the delicate part:

```
flag = 0
if mailbox is not empty:            ; a sender may have pushed after my last batch, but
    if xchg(flag, 1) == 0:          ; seen the flag still at 1 and not scheduled me
        process again               ; (if it returns 1, a sender already rescheduled me)
```

Clearing the flag and reading the mailbox is a store followed by a load: on x86 they can
be reordered (level 83), and then a message can be stranded with nobody scheduled to read
it. Put a fence there. That reordering is rare enough that the tests here may not catch
it, but real machines will.

## Gate

Write `actor_send` and `actor_run`. The harness runs 3 workers and 3 producer threads
sending 60 messages to 4 actors, under many schedules. Every message must be processed
exactly once and freed, each sender's messages in order, and no actor may ever run on two
workers at the same time.
