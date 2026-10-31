# Level 140 — System V ABI

*A function call is a contract between two pieces of code that have never met.
Linux, BSD and macOS on x86-64 all use the same one.*

## Lesson: the System V AMD64 calling convention

A **calling convention** is the set of rules that lets any function call any other:
where the arguments go, where the result comes back, and which registers a call may
wreck. The one used on x86-64 Unix systems is part of the *System V ABI* (application
binary interface):

| | Registers |
|---|---|
| integer/pointer arguments 1–6 | `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` (more go on the stack) |
| return value | `rax` (and `rdx` for a second half) |
| **caller-saved** ("scratch") | `rax`, `rcx`, `rdx`, `rsi`, `rdi`, `r8`–`r11`: any call may destroy them |
| **callee-saved** ("preserved") | `rbx`, `rbp`, `r12`–`r15`: a function must return them unchanged |
| also | `rsp` restored, DF clear on return; rsp 16-byte aligned at every `call` (next level) |

![The general-purpose registers by role: scratch registers (arguments and result) and preserved registers](registers.svg)

## Lesson: why the split is a good deal

Most functions are short. Because scratch registers need no saving, a short function
can use them freely and pay nothing. The cost appears only when a value must
**survive a call**: then you keep it in a preserved register, and save that register
first, because your own caller is relying on it too:

```
poly:
    push rbx            ; prologue: save the preserved registers we'll use
    push r12
    ...                 ; body: rbx and r12 now survive our calls
    pop r12             ; epilogue: restore them, in reverse order
    pop rbx
    ret
```

The **prologue** is the code at the start of a function that sets things up; the
**epilogue** undoes it before `ret`.

Note the argument order: `rcx` is the 4th argument here, but the `syscall` instruction
destroys rcx, which is why Linux syscalls pass their 4th argument in `r10` instead.

## Gate

Write `poly(x, a, b, c)` = a·x² + b·x + c (mod 2⁶⁴). Compute x² by calling the game's
`ring_square(x)` exactly once (declare it with `extern ring_square`). Like any
function, it destroys every caller-saved register.

The game checks the contract: rbx, rbp and r12–r15 unchanged, rsp restored, DF clear.
Constraints: at most 30 instructions; must use `call`, `push` and `pop`.
