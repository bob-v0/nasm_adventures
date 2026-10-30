# Level 110 — Non-blocking I/O

*Arc VI. One thread, many things happening at once: clients, timers, pipes. Your
program can only wait for one thing at a time, unless it stops waiting.*

## Lesson: blocking

Every `read` so far **blocked**: with no data, the kernel parked your process until data
arrived. With one input that's perfect. With two, it's a trap: while you wait on
descriptor A, descriptor B can have data piling up, and you won't notice until A says
something.

## Lesson: O_NONBLOCK and EAGAIN

A descriptor in **non-blocking** mode never parks you. A read that would wait returns
**−11, `EAGAIN`** ("try again") at once; a write that would wait does the same. Switch it
on with `fcntl` (syscall 72):

```
mov eax, 72             ; fcntl(fd, F_SETFL, O_NONBLOCK)
mov edi, 3
mov esi, 4              ; F_SETFL
mov edx, 0o4000         ; O_NONBLOCK
syscall
```

(Or pass `O_NONBLOCK` to `open`, `pipe2`, `socket`… when you create the descriptor.)
`EAGAIN` isn't an error, it's an answer. A read of **0** still means end of file.

## Lesson: polling, and its price

Now you can **poll**: try A, try B, repeat. When neither has anything, looping again at
once burns a CPU core asking "anything? anything?" millions of times a second. Sleeping
a little (`nanosleep`, syscall 35, with a `struct timespec { seconds, nanoseconds }`)
saves the CPU but adds delay. Neither is great: the next level fixes this properly.

## Lesson: data arrives in pieces

A pipe delivers bytes, not lines. A read can return half a line, or two and a half.
Keep a buffer per input, append what arrives, and only act on complete lines, keeping
the rest for later.

## Gate

Descriptors **3** and **4** are pipes from two sensors, A and B. Each sends lines at its
own pace, sometimes in pieces. Print each line as soon as it's complete, as `A: …` or
`B: …`, in the order the lines complete. When both pipes have closed, print `done` and
exit with 0.

The starter uses blocking reads, A then B. Run it and look at the order. The game's
clock is virtual: each syscall takes 1 µs, a sleep jumps ahead. A loop that never sleeps
runs out of its instruction budget (400 000) long before the sensors finish. Constraint:
at most 110 instructions.
