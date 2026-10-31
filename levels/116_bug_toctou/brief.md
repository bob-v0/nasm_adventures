# Level 116 — Bug: Time of Check, Time of Use ◆◆◆

*No shared memory, no threads, no signals. Just two processes and a filesystem, and a
check that was true when it was made.*

## Symptoms

`showfile` is a **privileged** helper: like a setuid-root program, it runs with root's
rights, so `open()` succeeds on any file. It is meant to show a user only the files *they*
may read. It checks first, with `access(path, R_OK)` (syscall 21), which answers for the
**real** user who ran it. Tested on its own, it's perfect: your own files print,
`/etc/shadow` is refused, even a symlink to `/etc/shadow` is refused.

Yet users of this machine are reading root's password hashes.

## Background: names are looked up again, every time

`access(path)` and `open(path)` each **resolve the name** from scratch: walk the
directories, follow the symlinks, find the file. Nothing guarantees that both find the
**same** file. Another process can change what the name means in between:

```
showfile                              another process
--------                              ---------------
access("/tmp/report")  → allowed      (it's the user's own file)
                                      delete /tmp/report
                                      symlink /tmp/report → /etc/shadow
open("/tmp/report")    → /etc/shadow
```

The check passed for the old file; the open gets the new one. This is a **TOCTOU** race
(time of check to time of use). It's a *logical* race: every syscall is atomic and
there's no shared memory, but the **sequence** isn't atomic.

The window is a few microseconds, so an attacker simply tries a million times.
Real-world TOCTOU bugs have broken `sudo`, package managers, container runtimes and
browsers.

## The fix: check the object, not the name

Resolve the name **once**, get a descriptor, and make every decision about the file the
descriptor refers to. Once open, a descriptor keeps pointing at the same file, whatever
happens to its name.

- `fstat(fd, &st)` (syscall 5) fills a 144-byte `struct stat` for an **open** file:
  `st_mode` is the dword at offset 24 (permission bits are its low 9 bits: 4 =
  readable by everyone), `st_uid`, the owner, is the dword at offset 28.
- `O_NOFOLLOW` (0o400000) makes `open` fail with `-ELOOP` if the last component is a
  symlink, a common extra layer.
- `openat(dirfd, name, ...)` (257) resolves `name` relative to an **open directory**.
  This pins the directories too, the same idea one level up.

## How the game tests it

The game's kernel can let another process act at an exact moment: right after your
program's *n*th call of some syscall. The final test puts the attacker's move
(*replace `/tmp/report` with a symlink to `/etc/shadow`*) after **every** syscall your
program makes, one run each. At every point your program must either print the file the
user is allowed to see, or refuse. It must never print the secret.

## Gate

1. Add a **witness**: the syscall after which the attacker strikes, as a line
   `;! witness after = "name"` (optionally `, nth = 2`), that makes the **original**
   print `/etc/shadow`.
2. Fix the program, changing at most **20 lines**. Print a file only if, **as opened**,
   it belongs to uid 1000 or is readable by everyone; otherwise write `access denied`
   and a newline to stderr and exit 1. Close what you open. Following a user's symlink is
   fine, and so is refusing every symlink.
