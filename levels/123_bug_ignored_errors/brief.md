# Level 123 — Bug: Ignored Errors ◆◆

*On the author's machine nothing ever fails. On a full disk, with the wrong
permissions or a dying drive, this program corrupts data and reports success.*

## Symptoms

`backup` copies config.txt to config.bak. When everything works, so does it. When
something fails, it does strange things: a missing file is "backed up", a failed
backup reports success, and some failures loop forever. Every failure must print one
message to stderr, exit with status 1, and close every file it opened.

## Background

Every syscall can fail, and on Linux failure is a **negative return value**: −errno.
Code that doesn't check properly ends up using an error code as if it were data:

- an error code mistaken for a file descriptor (−2 is not an fd; 0, on the other hand,
  is a perfectly valid one)
- a negative `read` result used as a length, where it becomes a huge unsigned count
- an unchecked `write` failure on a full disk (ENOSPC) silently losing data

Error paths are code too, and the least tested. They're where file descriptors and
memory leak. A long-running program that leaks a descriptor per failure eventually
can't open anything at all (EMFILE: too many open files).

## How the game tests it

The kernel *injects* failures on purpose: `open` returning EACCES, `read` returning EIO,
`write` returning ENOSPC on the first or a later call. The debugger's syscall log shows
each failure by name. The tests also check that only descriptors 0, 1 and 2 are open at
exit.

## Gate

Handle every failure as described in the starter's header comment, changing at most
**10 lines**.
