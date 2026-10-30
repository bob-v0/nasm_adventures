# Level 70 — x87 (Museum)

*Before SSE, x86 did floating point on a separate chip, the 8087, later built in. On
x86-64 it's a museum piece: compilers use SSE for float and double. But it's still there
in every CPU, still the only 80-bit `long double`, and it still has instructions SSE never
got: sine, cosine, tangent, logarithms.*

## Lesson: a stack of registers

The x87 FPU has eight 80-bit registers used as a **stack**: `st0` is the top, `st1` the
one below. Loading pushes, storing with `p` pops, and most instructions work on the top.

| instruction | effect |
|---|---|
| `fld qword [m]` | push a double from memory (`fild`: an integer) |
| `fld st2` | push a copy of st2 |
| `fstp qword [m]` | store st0 as a double, and pop (`fst`: no pop; `fistp`: an integer) |
| `fadd st0, st1` / `fmul qword [m]` | st0 = st0 + st1, st0 = st0 × [m] |
| `faddp st1, st0` / `fsubp st1, st0` | st1 = st1 + st0 (st1 − st0), pop: the result is the new st0 |
| `fxch st1` | swap st0 and st1 |
| `fsqrt`, `fsin`, `fcos` | replace st0 |
| `fsincos` | st0 = a becomes st0 = cos a, st1 = sin a |
| `fld1`, `fldz`, `fldpi` | push 1, 0, π |

Every push renames the registers: what was st0 is now st1. Write the stack in a comment
after each line, as the reference solutions in this game do.

There are no moves between the x87 and xmm registers: values go through memory. In a
leaf function the **red zone**, 128 bytes below rsp, is free scratch space.

## Lesson: the control word

`fnstcw [m]` stores the 16-bit **control word**, `fldcw [m]` loads it. Bits 10-11 are the
**rounding control** used by `fistp`, `frndint` and every arithmetic result:

| RC | rounding |
|---|---|
| 00 | to nearest, ties to even (the default) |
| 01 | down (toward −∞) |
| 10 | up (toward +∞) |
| 11 | toward zero |

Linux starts every process with **0x037F**: all exceptions masked, 64-bit precision,
round to nearest. Code that changes it must put it back.

## Lesson: the ABI

System V passes doubles in xmm0-xmm7 and returns them in xmm0 (and xmm1). The x87 stack
must be **empty** at every call and return (except a `long double` result in st0), and
the control word as the caller left it.

## Gate

`ring_rotate(x, y, angle)` rotates the point; returns x′, y′ in xmm0, xmm1 and
⌊√(x′² + y′²)⌋ in rax, with all the arithmetic on the x87.
