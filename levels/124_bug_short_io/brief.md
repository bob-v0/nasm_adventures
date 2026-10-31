# Level 124 — Bug: Short Reads, Short Writes ◆◆

*It works when you test it with a file. It loses data in production, where the input
comes through a pipe.*

## Symptoms

The program copies stdin to stdout. With a file as input, the output is complete. With
the same data arriving **through a pipe**, the output stops early, sometimes after a few
bytes.

## Background

`read(fd, buf, n)` returns **up to** n bytes: whatever is available right now. For a
regular file that's usually everything you asked for, which is why bugs here hide. For
pipes, terminals and network sockets, data arrives in pieces:

```
you ask:     read(0, buf, 4096)
pipe holds:  "hello wor"           (the rest is still on its way)
you get:     9
```

A pipe holds at most 64 KB, a terminal hands over one line at a time, a network packet
maybe 1500 bytes. Getting fewer bytes than you asked for is a **short read**, and it's
normal. Only a return value of **0** means "end of input".

`write` has the same property, the **short write**: when the receiver is slow, or the
call is interrupted by a signal, it can accept fewer bytes than you offered. The rest is
still yours to write.

Every robust C program wraps these calls in helpers like `read_full` / `write_all` for
this reason.

## How the game tests it

For the "pipe" tests the game's kernel delivers input in random-sized pieces and makes
stdout accept random-sized pieces, exactly as Linux may. The syscall log in the debugger
shows what each call returned.

## Gate

Make the copy complete under any combination of short reads and short writes. At most
**16 changed lines** (you'll be adding loops).
