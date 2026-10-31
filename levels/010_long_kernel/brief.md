# Level 10 — Long Kernel ★

*In Arc VI you wrote a shell that runs on Linux. Now Linux steps aside: your kernel
runs that shell.*

## The task

The kernel gets a **filesystem image** (`/bin` with Tiny Shell as `/bin/sh` and the game's
small programs: echo, cat, wc, head1, yes, true, false, pwd…; `/work` with the test's files;
`/tmp`) and a **script** on its console. It starts `/bin/sh` in `/work`, and the shell runs
the script: commands, `$?`, pipelines, `<` and `>`, `cd`, crashing programs. The tests are
level 111's own. When the shell exits, the kernel says:

```
shell exited with status 0
```

The starter has the whole arc (long mode, interrupts, address spaces, the ELF loader,
task switching) and the plumbing: a frame of every register for each system call,
dispatch through `calls`, `schedule`/`block`/`wake_all`, task creation, the filesystem
with path resolution, fd tables, `make_stack` with arguments. Yours is the Unix model:

| | |
|---|---|
| `fork` (57) | a copy of the calling process, which returns from the same call twice: with the child's pid, and with 0 |
| `execve` (59) | the same process, a new program: its memory replaced, its arguments on the new stack |
| `exit` (60), `wait4` (61) | an exited process lingers as a **zombie** until its parent collects its status |
| `pipe` (22) | a buffer with two ends; reading waits for data, writing waits for room |
| `open` (2), `close` (3), `dup2` (33) | descriptors pointing at shared open files, counted |
| `read` (0), `write` (1) | the console, files, pipes |
| `getcwd` (79), `chdir` (80) | the current directory, with `.` and `..` |

## Lesson: fork and exec

`fork` is strange the first time: one call, two returns. The kernel makes a new task
with a copy of the caller's memory and of its system call frame, so the child "returns"
from the same `syscall` with rax = 0, while the parent gets the child's pid. Then the
child calls `execve`, which throws its memory away and loads another program in the same
process: same pid, same open files (that's how redirection works: the shell sets up fds
0 and 1 between fork and exec).

## Lesson: file descriptors

![A pipeline: two processes, one pipe, the descriptors pointing at shared open files](pipeline.svg)

A descriptor is just an index into the process's table. What it points at is an
**open file** (the console, a file and its position, one end of a pipe), and several
descriptors, in several processes, can point at the same one: `fork` copies the table,
and `dup2` copies an entry. Each open file counts its references, and only when the
last one goes does the end of a pipe really close. That's when the reader sees the
end of its input, and a writer with no reader left gets -EPIPE.

## Lesson: waiting

Nothing here needs a timer. A process that can't go on (an empty pipe, a full one, no
zombie child yet) **blocks**: it stops being ready, and `schedule` runs someone else.
Whatever could change things (a write, a read, a close, an exit) wakes the waiters, and
each looks again. If everyone is waiting for everyone, the kernel says `deadlock`.

## Gate

Every Tiny Shell test: the output, in order, and the shell's exit status.
