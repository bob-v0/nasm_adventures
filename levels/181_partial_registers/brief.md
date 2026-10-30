# Level 181 — Nested Registers

*Each register turns out to contain smaller registers, like nesting dolls.*

## Lesson: register views

Every general-purpose register can be used at four sizes:

```
bit 63                               31              15       7      0
 |                rax                                                |
                                      |      eax                     |
                                                      |    ax        |
                                                      |  ah   | al   |
```

| 64-bit | 32-bit | 16-bit | low 8 | high 8 (bits 8–15) |
|---|---|---|---|---|
| rax | eax | ax | al | ah |
| rbx / rcx / rdx | ebx / ecx / edx | bx / cx / dx | bl / cl / dl | bh / ch / dh |
| rsi / rdi | esi / edi | si / di | sil / dil | – |
| r8 … r15 | r8d … r15d | r8w … r15w | r8b … r15b | – |

## Lesson: what happens to the upper bits

This rule surprises everyone the first time:

- Writing an **8-bit or 16-bit** register (`mov al, 5`) leaves all other bits unchanged.
- Writing a **32-bit** register (`mov eax, 5`) sets bits 63..32 of the full register to **zero**.

So `mov eax, 42` sets *all* of rax to 42. That is why NASM was happy to encode your
`mov rax, 42` in level 184 as the shorter `mov eax, 42`.

To widen a small value on purpose:

- `movzx` (**zero-extend**): fill the upper bits with 0. Use it for unsigned values.
- `movsx` / `movsxd` (**sign-extend**): fill the upper bits with copies of the top bit
  of the source. Use it for signed values: the 8-bit value 0xFF means −1, and
  sign-extending it to 64 bits gives 0xFFFF…FFFF, which is also −1.

`ah`/`bh`/`ch`/`dh` cannot be used in the same instruction as `sil`, `r8`–`r15` or
other registers that need the newer encoding (the REX prefix, level 56). For example,
`movzx rsi, ah` is rejected, but `movzx esi, ah` works and still clears all 64 bits.
Why does that work?

## Gate

On entry `rax` holds a value R. When your code finishes:

| Register | Must hold |
|---|---|
| `rbx` | the low byte of R, zero-extended |
| `rcx` | the low 16 bits of R, **sign**-extended to 64 bits |
| `rdx` | the low 32 bits of R, **sign**-extended to 64 bits |
| `rsi` | bits 8–15 of R (the `ah` byte), zero-extended |
| `rdi` | the low 32 bits of R, zero-extended |
| `r8`  | R with its low byte replaced by `0x7F` |

`rax` must still hold R. Constraints: at most 10 instructions; you must use `movzx`,
`movsx` and `movsxd`; no bitwise or shift instructions (`and`, `or`, `shl`, …).
Stretch goal: 7 instructions.
