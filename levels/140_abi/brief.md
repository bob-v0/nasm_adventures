# Level 140 — System V ABI

*A function call is a contract between two pieces of code that have never met.
Linux, BSD and macOS on x86-64 all use the same one.*

## Lesson: the System V AMD64 calling convention

| | Registers |
|---|---|
| integer/pointer arguments 1–6 | `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` (more go on the stack) |
| return value | `rax` (and `rdx` for a second half) |
| **caller-saved** ("scratch") | `rax`, `rcx`, `rdx`, `rsi`, `rdi`, `r8`–`r11`: any call may destroy them |
| **callee-saved** ("preserved") | `rbx`, `rbp`, `r12`–`r15`: a function must return them unchanged |
| also | `rsp` restored, DF clear on return; rsp 16-byte aligned at every `call` (next level) |

The split is a deal. A function may use the scratch registers freely, so short
functions need no saving at all. If it needs a value to **survive a call**, it keeps it
in a preserved register, and pays by saving that register first:

```
poly:
    push rbx            ; prologue: save what we'll use
    push r12
    ...                 ; body: rbx and r12 survive our calls
    pop r12             ; epilogue: restore in reverse order
    pop rbx
    ret
```

Note the argument order: `rcx` is the 4th argument here, but the `syscall` instruction
destroys rcx, which is why Linux syscalls pass their 4th argument in `r10`.

## Gate

Write `poly(x, a, b, c)` = a·x² + b·x + c (mod 2⁶⁴). Compute x² by calling the game's
`ring_square(x)` exactly once (declare it with `extern ring_square`). Like any
function, it destroys every caller-saved register.

The game checks the contract: rbx, rbp and r12–r15 unchanged, rsp restored, DF clear.
Constraints: at most 30 instructions; must use `call`, `push` and `pop`.
