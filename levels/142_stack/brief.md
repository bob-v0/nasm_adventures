# Level 142 — The Stack

*Arc IV. Your code learns to remember where it came from.*

## Lesson: the stack

`rsp` points at the top of a region of memory called the **stack**. Two instructions
use it:

```
push rax      ; rsp = rsp - 8, then [rsp] = rax
pop rbx       ; rbx = [rsp],   then rsp = rsp + 8
```

The stack **grows down**: each push moves rsp to a lower address. The last value
pushed is the first one popped (last in, first out), exactly what you need to reverse
things or to match nested brackets. In 64-bit mode `push`/`pop` move 8 bytes; there is
no single-byte push.

The stack is shared. Whatever is above rsp belongs to someone else: your caller,
and in the next level, the return address that lets your code get back. **Every push
needs a matching pop** (or an `add rsp, 8*n`), on every path out of your code. The
tests check that rsp ends where it started.

## Gate

The game provides `text` (NUL-terminated, up to 62 characters) and `out` (64 bytes of
garbage). Registers start poisoned.

1. Write `text` **reversed** into `out`, followed by a NUL byte. Use the stack.
2. `rax` = 1 if the brackets `()`, `[]`, `{}` in `text` are balanced and properly
   nested, else 0. Other characters are ignored.

rsp must end where it started. Constraints: at most 64 instructions; must use `push`
and `pop`.
