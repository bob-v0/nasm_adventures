# Level 139 — Stack Alignment

*Some library functions crash if the stack is off by 8 bytes. Here's why, and how
never to be the cause.*

## Lesson: the 16-byte rule

The ABI requires **rsp to be a multiple of 16 at every `call`** (rsp is *16-byte
aligned*). Since `call` then pushes an 8-byte return address, every function starts
with `rsp % 16 == 8`.

Why it matters: some SSE instructions, such as `movaps`, only work on 16-byte aligned
memory and fault otherwise. Compilers rely on the rule to keep 16-byte values on the
stack with those instructions. So `printf` and friends can crash with a segmentation
fault deep inside the library because **your** code misaligned the stack. Few bugs are
more confusing to track down.

Keeping the rule is simple arithmetic. Each `push` subtracts 8 from rsp, and
`sub rsp, n` subtracts n. Track `rsp % 16` from the entry value of 8; it must be 0 at
each call you make:

```
f:                  ; rsp % 16 == 8   (call pushed the return address)
    push rbx        ;            == 0
    push r12        ;            == 8   <- misaligned for a call!
    sub rsp, 8      ;            == 0   <- padding (or room for a local variable)
    call g          ; ok
    add rsp, 8
    pop r12
    pop rbx
    ret
```

A quick rule: with an **odd** number of pushes the stack is aligned; with an even
number (including zero), add 8 more bytes.

## Lesson: the red zone

The 128 bytes just **below** rsp are the *red zone*. A function that calls nobody (a
*leaf* function) may use them without moving rsp: signal handlers and the kernel
promise not to touch them. As soon as you `call`, the callee's pushes land right there,
so the red zone is only for leaves.

## Gate

Write `sum_squares(n, k)` = Σ (i·k)² for i = 1 … n (mod 2⁶⁴), computing each square
with the game's `ring_square(x)`, called exactly n times. This version counts every
call made with a misaligned stack, and the tests require zero.

Constraints: at most 32 instructions; must use `call`. The usual contract applies
(rbx, rbp, r12–r15, rsp, DF).
