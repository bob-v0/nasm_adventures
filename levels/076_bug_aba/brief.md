# Level 76 — Bug: ABA ◆◆◆◆

*The pointer is the same. The node is the same. Everything around it has changed, and
compare-and-swap can't tell.*

## Symptoms

A free list of 8 nodes, built as level 77's lock-free stack. Four threads repeatedly
pop a node, claim it (a `cmpxchg` of its owner field from 0 to their id, which would
notice another owner), use it, release it, and push it back. Very occasionally, a thread
pops a node that another thread is still using: "double owners".

## Background: ABA

`pop` does: read `top` (node A), read `A.next` (B), then `CAS(top, A → B)`. Between the
reads and the CAS:

```
thread 1: top = A, next = B ...          (preempted)
thread 2: pop A          -> top = B
thread 2: pop B          -> top = C      (B is now in use by thread 2)
thread 2: push A back    -> top = A, A.next = C
thread 1: CAS(top, A -> B)  succeeds: top is A!   -> top = B, which thread 2 owns
```

The CAS checks that `top` *equals* A, but the question that matters is whether it
*changed*. A went away and came back: **A → B → A**. With freed and reused memory it's
worse: `B` may be garbage.

ABA needs reuse, which is why level 77 didn't have it, and every real free list, memory
pool and object cache does.

## Background: fixes

- **Tagged pointers**: make the head `{ pointer, version }` and bump the version on every
  successful change. A CAS based on an old reading now fails even if the pointer came
  back. On x86-64, `lock cmpxchg16b` swaps both 8-byte halves at once (rdx:rax expected,
  rcx:rbx new). (Alternatives: steal unused pointer bits for a small counter; ARM's
  LL/SC instructions, which fail on *any* intervening write.)
- **Don't reuse while anyone might be looking**: safe memory reclamation (level 75).

## Gate

1. Add a witness: a schedule under which a node gets two owners:
   `;! witness schedule = N`. (Rare: look through many.)
2. Fix the stack, changing at most **24 lines**. The free list's head is 16 bytes,
   16-byte aligned, zeroed.
