# Level 15 — printk

*Every kernel has its own printf. Linux's is called printk, and it's the first thing
anyone debugging a kernel reaches for.*

## The task

Two functions, called the way C code calls them:

```
printk("%s: %d frames, %08x\r\n", "heap", 42, 0x1f)   →   heap: 42 frames, 0000001f
hexdump(address, 40)
```

| | |
|---|---|
| `%d` | signed decimal (a 64-bit argument) |
| `%u` | unsigned decimal |
| `%x` | hexadecimal, lowercase |
| `%p` | `0x` and 16 hex digits |
| `%s` | a string (0: `(null)`) |
| `%c` | one character |
| `%%` | a `%` |

Before the letter there can be a `-` (left-align), a `0` (pad numbers with zeros) and a
width: `%5d`, `%-8s`, `%08x`. printk returns how many characters it printed. hexdump
prints like `hexdump -C`:

```
0000000000080118  48 65 6c 6c 6f 2c 20 77  6f 72 6c 64 21 0a 00 01  |Hello, world!...|
0000000000080128  02 ff                                             |..|
```

## Lesson: variable arguments

In the C calling convention (System V), the first six integer arguments travel in
**rdi, rsi, rdx, rcx, r8, r9**, and the rest on the stack, the 7th at [rsp + 8] on entry.
printk's format is the first, so its values are rsi onwards. The trick every C library
uses is to spill the five registers next to the stack arguments, so that all arguments
form one array you can walk:

```
printk:
    push rbp
    mov rbp, rsp
    push r9                 ; [rbp - 8]
    push r8
    push rcx
    push rdx
    push rsi                ; [rbp - 40]: argument 0
                            ; arguments 5, 6, ...: [rbp + 16], [rbp + 24], ...
```

Nothing tells printk how many arguments there are. The format string does. That's
why a format that asks for more than was passed prints whatever is in those registers.

## Lesson: numbers in any base

The digits come out backwards: divide by the base, and the remainder is the last digit.
Write them from the end of a small buffer towards its start, then print forwards. For
`%d`, take the sign off first (`neg`), and remember it.

## Gate

Every format and dump, character for character, and every count printk returns.
