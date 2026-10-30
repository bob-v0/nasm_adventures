# Level 75 — Bug: Memory Reclamation ◆◆◆◆

*In a lock-free structure, "I removed it" doesn't mean "nobody is looking at it". The
hardest part of lock-free programming isn't the data structure; it's freeing memory.*

## Symptoms

Level 77's stack, with nodes from the heap: threads allocate and push values, pop and
free nodes as they go. The game's checked allocator stops it: **use after free**, a read
of `top.next` (in `pop`) inside a node another thread popped and freed a moment earlier.

## Background: why it happens

```
thread 1 (pop):  t = top (node X)               ... preempted
thread 2 (pop):  pops X, frees it
thread 1:        reads X.next                   <- freed memory
```

Thread 1's CAS would fail anyway, so the logic is fine. But the *read* already touched
freed memory, and with a real allocator that page may be unmapped (a crash) or reused
(garbage, or ABA). With locks this can't happen: nobody can free a node while you hold
the lock. Without locks, you need a way to know when **no thread can still be reading** a
node. That's **safe memory reclamation**, and it's why lock-free code is so much easier
in garbage-collected languages.

## Background: hazard pointers

Maged Michael's **hazard pointers** (2004):

- Each thread has a **hazard slot**. Before reading a node, it publishes the node's address
  there ("don't free this, I'm looking at it"), **fences** (store → load ordering again:
  level 83), then checks that the node is still reachable (`top` unchanged). If it is,
  nobody can have freed it before the hazard became visible.
- Removing a node doesn't free it: the thread **retires** it into a private list.
- Now and then the thread **scans**: every retired node that no hazard slot names is
  freed; the rest wait for the next scan.

Alternatives: **epoch-based reclamation** (threads announce which epoch they're in; nodes
retired in an epoch are freed when everyone has moved two epochs on, as in Rust's
`crossbeam`), and the Linux kernel's **RCU** (free after a "grace period" in which every
CPU has passed through a quiescent state).

## Gate

1. Add a witness: a schedule under which the original reads freed memory:
   `;! witness schedule = N`.
2. Fix it. Every node must still be freed by the end (the allocator checks for leaks),
   and no schedule may touch freed memory. `hazards` (one 64-byte slot per thread,
   zeroed) is ready for you.
