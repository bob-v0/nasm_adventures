# Level 94 — Instruction Selection

*Every instruction in the starter does what it says. Some of them just take ten times
longer than the alternative.*

## Lesson: what instructions really cost

The decoders turn instructions into **uops** (micro-operations), the units the
out-of-order engine schedules. Most simple instructions are one uop with a latency of 1,
but not all:

| instruction | cost on the game's CPU |
|---|---|
| `add`, `sub`, `lea`, `mov`, `movzx`, `shr` | 1 uop, latency 1 |
| `imul r, r, imm` | 1 uop, latency 3 |
| `div r32` | ~10 uops, latency 26, and the divider is busy for 24 cycles |
| `loop` | 7 uops (`dec` + `jnz`: 1, they fuse) |
| `push` / `pop` | a store / a load |

Real CPUs publish these numbers: Agner Fog's instruction tables and uops.info are the
references.

## Lesson: division by a constant

Dividing by a constant never needs `div`: `x / 10` is `(x * m) >> s` for a well-chosen
**magic number** `m`. For bytes, `(b * 205) >> 11` is exactly `b / 10` (205 / 2048 is
just above 1/10, and the error never reaches the next integer for b < 1024). Compilers do
this for every constant divisor; `x % 10` is then `x − 10·(x / 10)`, and `10q` is
`(q + 4q) · 2`, two cheap instructions.

## Lesson: partial registers

`mov al, [rdi]` writes 8 bits of `rax` and keeps the other 56, so the result depends on
the **old** `rax`, whatever wrote it last. That's a **false dependency**: it chains every
iteration to the previous one. `movzx eax, byte [rdi]` writes the whole register and
depends only on the memory. (Writing a 32-bit register zeroes the upper half for exactly
this reason.)

## Lesson: macro-fusion

`cmp`/`test`/`add`/`sub`/`and`/`inc`/`dec` directly followed by a conditional jump are
**fused** by the decoder into one uop. `loop` looks like a shortcut and isn't.

## Gate

`ring_digit_sum(bytes, n)` returns the sum of `b % 10` over n bytes. The starter takes
about 28 cycles per byte. Get it under **15** (2×); under 3 is possible.
