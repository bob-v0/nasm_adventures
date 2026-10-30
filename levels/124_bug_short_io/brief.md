# Level 124 — Bug: Short Reads, Short Writes ◆◆

*It works when you test it with a file. It loses data in production, where the input
comes through a pipe.*

## Symptoms

The program copies stdin to stdout. With a file as input, the output is complete. With
the same data arriving **through a pipe**, the output stops early, sometimes after a few
bytes.

## Background

`read(fd, buf, n)` returns **up to** n bytes: whatever is available right now. For a
regular file that's usually everything you asked for, which is why the bug hides. For
pipes, terminals and network sockets, data arrives in pieces: a pipe holds at most 64 KB,
a terminal hands over one line at a time, a network packet maybe 1500 bytes. Only a return
value of **0** means "end of input".

`write` has the same property: when the receiver is slow, or the call is interrupted by a
signal, it can accept fewer bytes than you offered, and the rest is still yours to
write.

So a correct copy has a loop on each side. Every robust C program wraps these calls in
helpers like `read_full` / `write_all`.

## How the game tests it

For the "pipe" tests the game's kernel delivers input in random-sized pieces and makes
stdout accept random-sized pieces, exactly as Linux may. The syscall log in the debugger
shows what each call returned.

## Gate

Make the copy complete under any combination of short reads and short writes. At most
**16 changed lines** (you'll be adding loops).
