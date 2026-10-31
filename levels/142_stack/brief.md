# Level 142 — The Stack

*Arc IV. Your code learns to remember where it came from.*

## Lesson: the stack

The **stack** is a region of memory that works like a pile of plates: you put things
on top and take them off the top. The register `rsp` (the *stack pointer*) holds the
address of the top plate. Two instructions use it:

```
push rax      ; rsp = rsp - 8, then [rsp] = rax
pop rbx       ; rbx = [rsp],   then rsp = rsp + 8
```

The stack **grows down**: each push moves rsp to a *lower* address. Here is what three
pushes do, starting from rsp = 0x1000:

```
  address    after push 'a', push 'b', push 'c'
  0x1000     (someone else's data)    <- rsp started here
  0x0ff8     'a'
  0x0ff0     'b'
  0x0fe8     'c'                       <- rsp now; pop gives 'c' first
```

The last value pushed is the first one popped (*last in, first out*). That is exactly
what you need to reverse a string, or to check that brackets close in the right order.
In 64-bit mode `push` and `pop` always move 8 bytes; there is no single-byte push.

## Lesson: leave it as you found it

The stack is shared. Whatever sits at rsp and above belongs to someone else: your
caller, and (from the next level on) the return address that lets your code get back.
So **every push needs a matching pop** (or an `add rsp, 8*n`) on every path out of your
code, including early exits. The tests check that rsp ends where it started.

## Gate

The game provides `text` (NUL-terminated, up to 62 characters) and `out` (64 bytes of
garbage). Registers start poisoned (filled with junk).

1. Write `text` **reversed** into `out`, followed by a NUL byte. Use the stack.
2. Set `rax` = 1 if the brackets `()`, `[]`, `{}` in `text` are balanced and properly
   nested, else 0. Other characters are ignored.

rsp must end where it started. Constraints: at most 64 instructions; must use `push`
and `pop`.
