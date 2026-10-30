# Level 91 — Threads

*Arc VIII. Until now one thing happened at a time, even with many tasks. Threads run
truly at the same time, on different cores, over the same memory. Everything that can
go wrong in this arc follows from that sentence.*

## Lesson: a thread

A **thread** is a second flow of execution in the same process: it shares the memory,
the open files and the signal handlers, but has its own **registers** and its own
**stack**. On Linux it's made with `clone` (syscall 56), the general version of `fork`:
flags choose what the new task shares.

```
clone(flags, stack, ptid, ctid, tls)
flags: CLONE_VM | CLONE_FS | CLONE_FILES | CLONE_SIGHAND | CLONE_THREAD | CLONE_SYSVSEM
       0x100      0x200      0x400         0x800           0x10000        0x40000
```

Like `fork`, it returns twice: the new thread's id (tid) in the caller, **0 in the new
thread**. The new thread starts **right after the `syscall`**, with `rsp = stack` and every
other register copied from the caller. That's how you hand it its work: put a pointer in
a register before calling `clone`. The stack is memory you provide (a `.bss` array,
`mmap`…). Pass its **top**: stacks grow down.

A thread ends with `exit` (60). That ends **only that thread**. `exit_group` (231) ends the
whole process: what C's `exit()` does.

## Lesson: joining

The caller has to wait until a thread has finished before using its result. Two `clone`
flags make this possible without polling:

- `CLONE_PARENT_SETTID` (0x100000): before `clone` returns, the kernel writes the tid at
  `ptid`;
- `CLONE_CHILD_CLEARTID` (0x200000): when the thread ends, the kernel writes **0** at
  `ctid` and wakes one futex waiter on it.

A **futex** ("fast userspace mutex", syscall 202) lets a thread sleep on a memory word:
`futex(addr, FUTEX_WAIT = 0, expected, 0)` sleeps **only if** `*addr` still equals
`expected` (checked atomically with going to sleep, or it returns at once), until
another thread calls `futex(addr, FUTEX_WAKE = 1, n)`. To join: while `tid != 0`, futex-wait
on it. That's exactly `pthread_join`.

## Lesson: the game's scheduler

On the game's machine all threads share one emulated CPU, and a scheduler decides who
runs when, down to single instructions. Tests run under many **schedules** (numbered
interleavings), so code that only works when threads happen to finish in time fails.

## Gate

`ring_parallel_sum(values, n, k)` returns the sum of `n` qwords, computed by `k` threads
(1–8). Split the array into `k` parts, start a thread per part, **join them all**, then
add up their results. The tests check that `k` threads really were created and none is
left running.
