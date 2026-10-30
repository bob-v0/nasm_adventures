# Level 139 — Stack Alignment

*Some library functions crash if the stack is off by 8 bytes. Here's why, and how
never to be the cause.*

## Lesson: the 16-byte rule

The ABI requires **rsp to be a multiple of 16 at every `call`**. Since `call` pushes
an 8-byte return address, every function starts with `rsp % 16 == 8`.

Why it matters: SSE instructions such as `movaps` require 16-byte aligned memory and
fault otherwise. Compilers rely on the rule to keep 16-byte values on the stack, so
`printf` and friends can crash with a segmentation fault deep inside the library when
**your** code misaligned the stack. Few bugs are more confusing to find.

Keeping it is arithmetic: each `push` subtracts 8, and `sub rsp, n` subtracts n. Before
each call you make, the total moved since entry must be ≡ 8 (mod 16):

```
f:                  ; rsp % 16 == 8
    push rbx        ;            == 0
    push r12        ;            == 8   <- misaligned for a call!
    sub rsp, 8      ;            == 0   <- padding (or a local variable)
    call g          ; ok
    add rsp, 8
    pop r12
    pop rbx
    ret
```

## Lesson: the red zone

The 128 bytes **below** rsp are the *red zone*: a function that calls nobody may use
them without moving rsp, since signal handlers and the kernel won't touch them. Once
you `call`, the callee's pushes land there, so it's only for leaf functions.

## Gate

Write `sum_squares(n, k)` = Σ (i·k)² for i = 1 … n (mod 2⁶⁴), computing each square
with the game's `ring_square(x)`, called exactly n times. This version counts every
call made with a misaligned stack, and the tests require zero.

Constraints: at most 32 instructions; must use `call`. The usual contract applies
(rbx, rbp, r12–r15, rsp, DF).
