# Level 175 — Speak

*For the first time, your program can say something.*

## Lesson: file descriptors

A Linux process talks to the outside world through numbered **file descriptors**.
Three are open from the start:

| fd | name | usually |
|---|---|---|
| 0 | stdin | the keyboard / piped input |
| 1 | stdout | normal output |
| 2 | stderr | error and diagnostic messages |

## Lesson: `write`

```
mov eax, 1          ; syscall 1 = write
mov edi, 1          ; fd: stdout
mov rsi, msg        ; address of the bytes
mov edx, MSG_LEN    ; how many bytes
syscall             ; rax = bytes written (or -errno)
```

`write` doesn't care about text or terminators; it copies exactly `count` bytes. Strings
in NASM:

```
msg: db "Hi", 10        ; double quotes: no escapes, so add 10 (newline) by hand
msg: db `Hi\n`          ; backquotes: C-style escapes \n \t \0 \x41 ...
MSG_LEN equ $ - msg
```

## Lesson: return values

Every syscall leaves its result in `rax`, so the next syscall number you load
**overwrites** it. If you need a result, copy it somewhere first. Remember that
`rcx` and `r11` are destroyed by every `syscall`, so don't keep anything there.

## Gate

The game provides `name` (8 bytes, different in each test) and `NAME_LEN`.

- stdout: `Hello, ` then the 8 bytes of `name` then `!` and a newline
- stderr: `warning: the walls have ears` and a newline
- exit status: the value **returned by your stderr write**

Constraint: at most 30 instructions.

## Try this

Run your program outside the game: `./solution 2>/dev/null` hides stderr, and
`./solution >/dev/null` hides stdout. Separate streams are the reason fd 2 exists.
