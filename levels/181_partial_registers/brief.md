# Level 181 — Nested Registers

*Each register turns out to contain smaller registers, like nesting dolls.*

## Lesson: register views

You can use every general-purpose register at four sizes. The smaller names are not
separate registers: they are **views** of the low part of the same 64 bits.

![rax contains eax, which contains ax, which is made of ah and al](register-views.svg)

```
bit 63                               31              15       7      0
 |                rax                                                |
                                      |      eax                     |
                                                      |    ax        |
                                                      |  ah   | al   |
```

So if rax holds `0x1122334455667788`, then eax is `0x55667788`, ax is `0x7788`,
ah is `0x77` and al is `0x88`.

| 64-bit | 32-bit | 16-bit | low 8 | high 8 (bits 8–15) |
|---|---|---|---|---|
| rax | eax | ax | al | ah |
| rbx / rcx / rdx | ebx / ecx / edx | bx / cx / dx | bl / cl / dl | bh / ch / dh |
| rsi / rdi | esi / edi | si / di | sil / dil | – |
| r8 … r15 | r8d … r15d | r8w … r15w | r8b … r15b | – |

## Lesson: what happens to the upper bits

This rule surprises everyone the first time:

- Writing an **8-bit or 16-bit** register (`mov al, 5`) leaves all the other bits
  unchanged.
- Writing a **32-bit** register (`mov eax, 5`) sets bits 63..32 of the full register
  to **zero**.

So `mov eax, 42` sets *all* of rax to 42. That is why NASM was happy to encode your
`mov rax, 42` in level 184 as the shorter `mov eax, 42`.

## Lesson: widening a small value

Often you have a small value (a byte, say) and want it in a full 64-bit register.
How you fill the new upper bits depends on what the value means:

- `movzx` (**zero-extend**) fills the upper bits with 0. Use it for unsigned values:
  the byte 0xFF (255) becomes 0x0000…00FF, still 255. It only takes an 8- or 16-bit
  source. There is **no `movzx rdi, eax`**: to zero-extend 32 bits you just write the
  32-bit register, `mov edi, eax`, thanks to the rule above. Intel never needed a
  separate instruction for it.
- `movsx` / `movsxd` (**sign-extend**) fill the upper bits with copies of the top bit
  of the source. Use them for signed values: the 8-bit value 0xFF means −1, and
  sign-extending it to 64 bits gives 0xFFFF…FFFF, which is also −1. From 32 bits the
  instruction is called `movsxd rdi, eax` (NASM also accepts `movsx` for it).

One oddity: `ah`/`bh`/`ch`/`dh` cannot appear in the same instruction as `sil`,
`r8`–`r15` or any other register that needs the newer encoding (the REX prefix,
level 56). For example, `movzx rsi, ah` is rejected, but `movzx esi, ah` works and
still clears all 64 bits of rsi. Why does that work?

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
