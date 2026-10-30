# Level 118 — Bug: Reentrant Signal Handler ◆◆◆

*The bug appears once in a few hundred runs, only when a signal lands on exactly the
wrong instruction. The game can deliver it on every instruction in turn.*

## Symptoms

The program prints 1 to 20, and a line `signal` whenever SIGUSR1 arrives. Most of the
time the output is perfect. Sometimes a number is replaced by `signal`, or printed twice,
or `signal` appears twice.

## Background: reentrancy

A signal handler runs **in the middle of** whatever the program was doing, possibly
halfway through a function that the handler then calls again. That function is now
running twice at once, and both copies share its global state. A function is
**reentrant** if that's safe.

`print_number` isn't: it formats into the shared buffer `out`, stores the start and length
in globals, *then* writes. If the handler's `print_text` runs in between, it rewrites the
same buffer and globals, and the main program writes the handler's text instead of its
number.

This is why POSIX lists the few **async-signal-safe** functions a handler may call.
`printf` and `malloc` are not among them: they use shared buffers and locks, just like
this program. C's `errno` is the subtle version of the same problem: a handler that makes
a syscall can overwrite the `errno` the main program is about to read.

## The safe pattern

Do as little as possible in the handler: **record** that the signal happened (set or
increment a flag in a single instruction) and let the main program **act** on it at a safe
point. Production servers handle SIGTERM, SIGHUP and SIGCHLD this way.

## How the game tests it

One test delivers SIGUSR1 **after every single instruction** of the program, in turn,
from the moment the handler is installed until just before exit, and checks the output
each time. The report says where the signal landed.

## Gate

Make the output correct wherever the signal lands, changing at most **12 lines**.
