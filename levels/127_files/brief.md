# Level 127 — Files

*Arc V. Your program meets the operating system for real: files, memory, processes,
signals, time. From here on the game runs your code on its own emulated Linux kernel,
which can also make things go wrong on purpose.*

## Lesson: file descriptors

`open` asks the kernel for access to a file and returns a **file descriptor** (fd): a
small integer that names the open file in later calls. Think of it as a ticket number
for a row in a table the kernel keeps for your process:

```
fd   refers to
0    stdin       ┐
1    stdout      │ already open when your program starts
2    stderr      ┘
3    in.txt      ← the first open usually gets 3
4    out.txt     ← the next one 4
```

```
mov eax, 2              ; open(path, flags, mode)
lea rdi, [path]         ; a C string: "in.txt", 0
mov esi, 0              ; O_RDONLY
syscall                 ; rax = fd, or -errno
```

The `flags` say how you'll use the file. Combine them with `|`:

| flag | value | meaning |
|---|---|---|
| `O_RDONLY` / `O_WRONLY` / `O_RDWR` | 0 / 1 / 2 | read only / write only / both |
| `O_CREAT` | 0o100 | create it if it doesn't exist (then `mode` sets its permissions) |
| `O_TRUNC` | 0o1000 | empty it first |
| `O_APPEND` | 0o2000 | every write goes to the end |

Relative paths are relative to the current directory (here `/work`). `close(fd)`
(syscall 3) gives the descriptor back. A process has a limited number of them, and
leaking them is a classic bug.

## Lesson: errors

Syscalls report failure by returning **−errno**, a negative error number: `open` on a
missing file returns −2 (ENOENT), on a forbidden one −13 (EACCES). C's `open` returns −1
and stores the errno in a variable; at the syscall level you get it directly in rax.
Every syscall can fail, so check every result.

## Lesson: reading a whole file

`read(fd, buf, n)` returns *up to* n bytes, and **0 at the end of the file**. A file
bigger than your buffer needs a loop: read, handle the chunk, read again, until 0.

## Gate

In `/work`:

1. Open `in.txt` for reading. If that fails, write `cannot open in.txt` and a newline to
   **stderr** and exit with the **errno** as the status (2 for a missing file).
2. Copy its contents to `out.txt` (create it, or truncate it if it exists, mode 0644),
   using a buffer of at most 4096 bytes.
3. Print `N lines` and a newline to stdout, where N is the number of newline bytes.
4. Close both files and exit with 0.

The tests check out.txt, and that only descriptors 0, 1 and 2 are open at exit.
Constraint: at most 70 instructions.
