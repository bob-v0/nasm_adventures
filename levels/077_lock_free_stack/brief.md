# Level 77 — Lock-Free Stack

*No lock, no waiting, no thread ever blocked by another, and still correct. The trick:
make everything hinge on one word.*

## Lesson: lock-free

With a lock, a thread that's preempted (or crashes, or is slow) while holding it stops
everyone. A **lock-free** data structure guarantees that *some* thread always completes
its operation in a bounded number of steps, whatever the others are doing. Nobody ever
waits for anybody; at worst you retry because someone else succeeded.

## Lesson: the Treiber stack

R. Kent Treiber's stack (IBM, 1986) is the simplest lock-free structure. The whole state
that threads share is **one pointer**, the top, and it only ever changes through
compare-and-swap:

```
push(node):  repeat:  t = top
                      node.next = t
             until CAS(&top, t, node)          ; still t? then node is the new top

pop():       repeat:  t = top
                      if t == 0: return 0
                      n = t.next
             until CAS(&top, t, n)             ; still t? then n is the new top
             return t
```

If another thread changed `top` in between, the CAS fails, `cmpxchg` hands you the new
`top` in `rax`, and you retry with it. Each operation takes effect at the instant its
successful CAS happens: its **linearization point**.

## Lesson: what can still go wrong

`pop` reads `t.next` before its CAS. By then another thread may already have popped
`t`... If nodes are never reused or freed, reading it is harmless (the CAS will fail).
If they are, that one read is the source of the two hardest bugs in lock-free
programming: **ABA** (level 76) and **use after free** (level 75). In this level nodes are
never reused.

## Gate

Write `stack_push` and `stack_pop` without any lock. The game's harness runs 4 threads
pushing and popping at the same time, under store buffers and many schedules; every node
must come out exactly once. Constraint: at most 20 instructions.
