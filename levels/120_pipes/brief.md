# Level 120 — Pipes & dup

*`ls | grep x | wc -l`: three programs that know nothing about each other, glued together
by the kernel. Here you build the glue.*

## Lesson: pipes

`pipe(fds)` (syscall 22) creates a **pipe**, a buffer inside the kernel, and gives you
two new descriptors in an `int fds[2]`: `fds[0]` is the **read end**, `fds[1]` the
**write end**. Bytes written to one come out of the other, in order.

- A read from an empty pipe **waits** for data, or returns **0** (end of file) once
  **every** write end in **every** process is closed.
- A write to a full pipe (64 KiB here) **waits** for a reader to make room. A write to a
  pipe whose read ends are **all** closed fails with `-EPIPE`, and the kernel first sends
  the writer **SIGPIPE**, which kills it by default. That is how `yes | head -1` ends.

`pipe2(fds, flags)` (293) is the same with flags such as `O_CLOEXEC`.

## Lesson: dup2

`dup2(old, new)` (syscall 33) makes descriptor `new` refer to the same open file as
`old`, closing whatever `new` was first.

Why that's enough to build a pipeline: programs read from descriptor 0 and write to 1
without knowing what they are. So a shell **redirects** a command by fixing up 0 and 1
in the child, between `fork` and `execve`. Descriptors survive the `execve`:

```
child:  dup2(fds[1], 1)     ; my stdout is now the pipe's write end
        close(fds[0])       ; and I don't need the originals any more
        close(fds[1])
        execve(...)
```

![A pipeline: the left child's fd 1 is the pipe's write end, the right child's fd 0 its read end](pipeline.svg)

## Lesson: close what you don't use

After `fork`, both processes hold copies of both pipe ends. Every copy counts:

- If the parent (or the reader itself!) still holds a **write end**, the reader never
  sees end-of-file and waits forever.
- If anyone still holds the **read end**, a writer like `yes` never gets SIGPIPE. It
  fills the pipe and waits forever.

When every process is waiting for another one, that's a **deadlock**. The game's kernel
detects it and tells you who was waiting for what.

## Gate

The arguments describe a pipeline: `LEFT... | RIGHT...`, with `|` as an argument of its
own, for example

```
./solution /bin/echo one two | /bin/wc
```

Run both commands **at the same time**: LEFT with its stdout going into a pipe, RIGHT with
that pipe as its stdin. Each command's argv is its part of your argv (`argv[0]` is the
program's path). Pass your envp on. Wait for both, then exit with RIGHT's status (its
exit code, or 128 + the signal if it was killed), like a shell does.

The tests check that only descriptors 0, 1 and 2 are open at your exit, and that you
left no zombies. They use different turn lengths for the processes. Constraint: at most
110 instructions.
