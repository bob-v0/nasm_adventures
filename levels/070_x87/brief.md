# Level 70 — x87 (Museum)

*Before SSE, x86 did floating point on a separate chip, the 8087, later built in. On
x86-64 it's a museum piece: compilers use SSE for float and double. But it's still there
in every CPU, still the only 80-bit `long double`, and it still has instructions SSE never
got: sine, cosine, tangent, logarithms.*

## Lesson: a stack of registers

The x87 **FPU** (floating-point unit) has eight 80-bit registers, used as a **stack**.
`st0` is the top, `st1` the one below it, and so on. Loading a value pushes it; a store
whose name ends in `p` pops; most instructions work on the top.

| instruction | effect |
|---|---|
| `fld qword [m]` | push a double from memory (`fild`: an integer) |
| `fld st2` | push a copy of st2 |
| `fstp qword [m]` | store st0 as a double, and pop (`fst`: no pop; `fistp`: as an integer) |
| `fadd st0, st1` / `fmul qword [m]` | st0 = st0 + st1, st0 = st0 × [m] |
| `faddp st1, st0` / `fsubp st1, st0` | st1 = st1 + st0 (st1 − st0), pop: the result is the new st0 |
| `fxch st1` | swap st0 and st1 |
| `fsqrt`, `fsin`, `fcos` | replace st0 |
| `fsincos` | st0 = a becomes st0 = cos a, st1 = sin a |
| `fld1`, `fldz`, `fldpi` | push 1, 0, π |

The catch: every push renames the registers. What was st0 is now st1. Write the stack
in a comment after each line, as the reference solutions in this game do:

```
fld  qword [rsp-8]     ; st0 = x
fld  qword [rsp-16]    ; st0 = y, st1 = x
fmul st0, st1          ; st0 = y·x, st1 = x
```

There are no moves between x87 and xmm registers: values go through memory. In a leaf
function (one that calls nothing) the **red zone**, the 128 bytes below rsp, is free
scratch space.

## Lesson: the control word

The 16-bit **control word** sets how the FPU behaves. `fnstcw [m]` stores it to memory,
`fldcw [m]` loads it. Bits 10–11 are the **rounding control**, used by `fistp`,
`frndint` and every arithmetic result:

| RC | rounding |
|---|---|
| 00 | to nearest, ties to even (the default) |
| 01 | down (toward −∞) |
| 10 | up (toward +∞) |
| 11 | toward zero |

Linux starts every process with **0x037F**: all exceptions masked, 64-bit precision,
round to nearest. Code that changes it must put it back.

## Lesson: the ABI

System V passes doubles in xmm0–xmm7 and returns them in xmm0 (and xmm1). The x87 stack
must be **empty** at every call and return (except for a `long double` result in st0),
and the control word must be as the caller left it.

## Gate

`ring_rotate(x, y, angle)` rotates the point (x, y) by `angle` radians around the
origin. Return x′ in xmm0, y′ in xmm1, and ⌊√(x′² + y′²)⌋ (the length, rounded down) in
rax.

The tests check that:

- all the arithmetic is on the x87 (xmm registers only move values in and out), using
  `fsincos` (or `fsin` and `fcos`), `fsqrt`, and `fldcw` to round down;
- the control word is back to 0x037F when you return;
- the x87 stack is empty when you return.
