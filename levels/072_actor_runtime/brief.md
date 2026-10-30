# Level 72 — Lock-Free Actor Runtime ★

*The last gate of Arc VIII. Threads, atomics, memory ordering, futexes, lock-free
mailboxes, reference counts and shutdown: everything at once, under a scheduler that
tries the interleavings you'd rather not think about.*

## The task

Write a complete actor runtime:

| function | does |
|---|---|
| `rt_init(workers)` | starts that many worker threads (at most 8) |
| `actor_new(behavior)` | a new actor on the heap, holding one reference for its creator |
| `actor_send(actor, msg)` | from any thread, including from inside a behavior |
| `actor_release(actor)` | drops a reference; the last one frees the actor |
| `rt_shutdown()` | waits until every message sent has been handled, then stops the workers and waits for them |

Workers call an actor's `behavior(actor, msg)` for each of its messages: in order, and
never on two workers at once. A message is `dq next, dq value`; the behavior frees it.
Use the game's checked allocator (`syscall` 0x1000 = `malloc(rdi)`, 0x1001 = `free(rdi)`).

## The test

Four actors in a ring pass tokens around: a message with value `h > 0` makes the
behavior send `h − 1` to the next actor. Two producer threads inject three tokens each,
six hops long. Then the harness calls `rt_shutdown` and releases the actors. Under the
plain schedule and many others, with x86 store buffers:

- every one of the 42 messages is handled exactly once;
- no actor ever runs on two workers at once;
- the checked allocator sees no use after free, no double free and no leak;
- no thread is left running.

## What you need (and where you learned it)

- worker threads and joining: level 91;
- a run queue whose workers sleep: levels 87 and 80;
- MPSC mailboxes, the scheduled flag and going idle safely: level 74;
- reference counts: level 73. Who holds the references (the creator, and the run queue
  while an actor is queued or running) decides when an actor may be freed;
- **quiescence** for shutdown: count the messages in flight (increment *before* a message
  becomes visible, decrement after its behavior returns), and let the last decrement
  wake `rt_shutdown`. Messages sent from inside behaviors keep the count above zero until
  the whole ring has gone quiet.

Arc VIII cleared. Next: floating point and SIMD.
