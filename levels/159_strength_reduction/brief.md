# Level 159 — Strength Reduction

*`div` takes dozens of cycles. A multiply takes three. Compilers know a trick, and
now so will you.*

## Lesson: cheaper operations

**Strength reduction** replaces an expensive operation with cheaper ones that compute
the same thing:

| Instead of | Use | Why |
|---|---|---|
| x × 8, x / 8 (unsigned) | `shl`, `shr` by 3 | shifts cost one cycle |
| x × 3, 5, 9 | `lea r, [x + x*2]` (×3), `[x + x*4]` (×5), `[x + x*8]` (×9) | one cycle, no flags touched |
| x × 45 | two `lea`s: ×5 then ×9 | still faster than `imul` on old CPUs |
| x / 10 | multiply by a "magic" reciprocal | `div` is 20–90 cycles |

## Lesson: dividing by multiplying

Dividing by 10 is multiplying by 1/10. In fixed point: pick m ≈ 2⁶⁷ / 10, multiply, and
shift away the 67 fractional bits:

```
x / 10  =  (x × 0xCCCC_CCCC_CCCC_CCCD) >> 67      exactly, for every 64-bit x
```

`mul` produces the 128-bit product in rdx:rax, so rdx already holds `product >> 64`;
three more bits of `shr` finish the job. Proving that a magic number is exact for every
input is a lovely piece of number theory (see *Hacker's Delight*, chapter 10). Every
compiler does this whenever you divide by a constant.

## Gate

On entry `rdi` = x (unsigned). When your code finishes:

| Register | Must hold |
|---|---|
| `rax` | x / 10 |
| `rbx` | x % 10 |
| `rcx` | x × 45 (low 64 bits) |
| `r8` | x / 8 |
| `r9` | x × 1024 (low 64 bits) |

`rdi` must be unchanged. Constraints: at most 16 instructions; no `div`, `idiv` or
`imul`. `mul` is allowed.
