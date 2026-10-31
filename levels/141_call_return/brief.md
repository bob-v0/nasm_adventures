# Level 141 — Call & Return

*Code you write once and use from anywhere: functions.*

## Lesson: call and ret

A **function** is a piece of code you can jump into from anywhere and that knows how
to get back. Two instructions do it:

```
    call utoa       ; push the address of the next instruction, then jump to utoa
    ...             ; ...and execution continues here when utoa returns
utoa:
    ...
    ret             ; pop that address and jump to it
```

The address `call` pushes is the **return address**. So a call is just a jump that
leaves a note on the stack saying where to come back to.

![call pushes the return address and jumps; ret pops it and jumps back](call-ret.svg)

A function can call other functions, because each `call` pushes its own return
address on top of the others. The one rule: when `ret` runs, rsp must point at that
return address again, exactly as `call` left it. Leave an extra push behind and `ret`
jumps to whatever value you pushed.

## New: function levels

From this level on, the game often **calls your function** instead of running your
code top to bottom, just as other code would:

- arguments arrive in `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9`, in that order
- you return the result in `rax`, with `ret`
- **`rbx`, `rbp` and `r12`–`r15` must come back unchanged**. If you use them, push them
  first and pop them before returning. Every other register is yours.
- everything else starts with garbage

Export the function so the game can find it: `global print_uint` and a
`print_uint:` label. Level 140 explains the full calling convention.

## Gate

Write `print_uint(n)`: print the unsigned decimal value of n followed by a newline to
stdout (with the `write` syscall) and return the number of bytes written.

Structure it as **at least two functions**: a helper that formats the number, called
from `print_uint`. You have a formatter in your library from level 154; this is where
it becomes a reusable function. Constraints: at most 60 instructions; must use `call`
and `ret`. Passing adds `print_uint` to your library.
