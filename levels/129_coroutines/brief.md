# Level 129 — Coroutines

*Two functions taking turns, each with its own stack, each picking up exactly where
it left off.*

## Lesson: coroutines

A normal function runs to completion and returns. A **coroutine** can *suspend*
partway, let someone else run, and later *resume* where it stopped, with all its local
state intact. Generators (`yield` in Python), async/await (Arc VI), green threads and
operating system threads (Arc XII) are all built on the same trick:

**Give each coroutine its own stack, and switch between stacks.**

## Lesson: a context switch

The state of a suspended coroutine is just:

- its **stack pointer** (its stack holds its return addresses and locals)
- its **callee-saved registers** (rbx, rbp, r12–r15)

Scratch registers needn't be saved: the switch is called like a function, so the
code calling it already expects them to be destroyed. That's why a context switch is
cheap:

```
co_switch(save, load):
    save rsp, rbx, rbp, r12, r13, r14, r15 into *save
    load rsp, rbx, rbp, r12, r13, r14, r15 from *load
    ret            ; pops a return address from the NEW stack: we're in the other context
```

To start a coroutine for the first time, give it a stack whose top holds the address of
its entry function, and a context whose rsp points there. The first switch "returns"
into it.

## Gate

Write `co_switch(save, load)`. Each context is 7 qwords: **rsp, rbx, rbp, r12, r13,
r14, r15**, in that order.

The game's `ring_fib(n)` runs a Fibonacci generator as a coroutine on its own stack,
resuming it n times. The generator keeps its numbers in r12 and r13, and the caller
uses the same registers for its own state, so they only survive if your switch saves
and restores them per context. Constraints: at most 20 instructions; must use `ret`.
