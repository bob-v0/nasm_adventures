# Level 91 — Threads

*Arc VIII. Until now one thing happened at a time, even with many tasks. Threads run
truly at the same time, on different cores, over the same memory. Everything that can
go wrong in this arc follows from that sentence.*

## Lesson: a thread

A **thread** is a second flow of execution in the same process. It shares the memory,
the open files and the signal handlers, but has its own **registers** and its own
**stack**. On Linux you make one with `clone` (syscall 56), the general version of
`fork`: its flags choose what the new task shares with you.

```
clone(flags, stack, ptid, ctid, tls)
flags: CLONE_VM | CLONE_FS | CLONE_FILES | CLONE_SIGHAND | CLONE_THREAD | CLONE_SYSVSEM
       0x100      0x200      0x400         0x800           0x10000        0x40000
```

Like `fork`, it returns twice:

```
             ┌── caller:      rax = the new thread's id (tid); carries on
clone(...) ──┤
             └── new thread:  rax = 0, rsp = stack, every other register copied
```

The new thread starts **right after the `syscall`**. Since it gets a copy of your
registers, that's how you hand it its work: put a pointer in a register before calling
`clone`. The stack is memory you provide (a `.bss` array, `mmap`…). Pass its **top**:
stacks grow down.

A thread ends with `exit` (60), which ends **only that thread**. `exit_group` (231) ends
the whole process: it's what C's `exit()` does.

## Lesson: joining

Before you use a thread's result, you have to wait until it has finished: you **join**
it. Two `clone` flags make that possible without polling:

- `CLONE_PARENT_SETTID` (0x100000): before `clone` returns, the kernel writes the tid at
  `ptid`;
- `CLONE_CHILD_CLEARTID` (0x200000): when the thread ends, the kernel writes **0** at
  `ctid` and wakes one futex waiter on it.

A **futex** ("fast userspace mutex", syscall 202) lets a thread sleep on a memory word.
`futex(addr, FUTEX_WAIT = 0, expected, 0)` sleeps **only if** `*addr` still equals
`expected` (checked atomically with going to sleep; otherwise it returns at once), until
another thread calls `futex(addr, FUTEX_WAKE = 1, n)`. So to join: while `tid != 0`,
futex-wait on it.

```
caller:  clone ──────── futex_wait(&tid, tid) ··· asleep ···   wakes: tid == 0, joined
worker:         adds up its part ── exit ── kernel: tid = 0, wake ──┘
```

That's exactly `pthread_join`.

## Lesson: the game's scheduler

On the game's machine all threads share one emulated CPU, and a scheduler decides who
runs when, down to single instructions. Tests run under many **schedules** (numbered
interleavings), so code that only works when threads happen to finish in time fails.

## Gate

`ring_parallel_sum(values, n, k)` returns the sum of `n` qwords, computed by `k` threads
(1–8). Split the array into `k` parts, start a thread per part, **join them all**, then
add up their results. The tests check that the work really ran on `k` threads (yours may
count as one of them, so at least `k − 1` calls to `clone`) and that no thread you
started is still running when you return.
