# Level 175 — Speak

*For the first time, your program can say something.*

## Lesson: file descriptors

A Linux program talks to the outside world through **file descriptors**: small
numbers that each stand for an open file, terminal, pipe or network connection.
Three are open from the start:

| fd | name | usually |
|---|---|---|
| 0 | stdin | the keyboard / piped input |
| 1 | stdout | normal output |
| 2 | stderr | error and diagnostic messages |

## Lesson: `write`

`write` is syscall 1. It takes a file descriptor, the address of some bytes and how
many bytes to send:

```
mov eax, 1          ; syscall 1 = write
mov edi, 1          ; fd: stdout
mov rsi, msg        ; address of the bytes
mov edx, MSG_LEN    ; how many bytes
syscall             ; rax = bytes written (or -errno)
```

`write` knows nothing about text or terminators: it copies exactly `count` bytes,
starting at the address. Strings in NASM:

```
msg: db "Hi", 10        ; double quotes: no escapes, so add 10 (newline) by hand
msg: db `Hi\n`          ; backquotes: C-style escapes \n \t \0 \x41 ...
MSG_LEN equ $ - msg
```

## Lesson: return values

Every syscall leaves its result in `rax`. The moment you load the next syscall
number, that result is **overwritten**, so if you need it, copy it somewhere first.
And remember that every `syscall` destroys `rcx` and `r11`, so don't keep anything
there.

## Gate

The game provides `name` (8 bytes, different in each test) and `NAME_LEN`.

- stdout: `Hello, ` then the 8 bytes of `name` then `!` and a newline
- stderr: `warning: the walls have ears` and a newline
- exit status: the value **returned by your stderr write**

Constraint: at most 30 instructions.

## Try this

Run your program outside the game, in {{terminal}}: `./solution 2>/dev/null` hides
stderr, and `./solution >/dev/null` hides stdout. Being able to separate the two is
the reason fd 2 exists.
