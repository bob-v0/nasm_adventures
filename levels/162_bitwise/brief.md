# Level 162 — Bitwise Logic

*Memory comes in 4096-byte pages, and the operating system thinks in pages. So will
you.*

## Lesson: bitwise operations

These instructions work on each bit position on its own, with no carries between
positions:

```
and rax, rbx     ; 1 only where both are 1   -> clear bits (keep where mask is 1)
or  rax, rbx     ; 1 where either is 1       -> set bits
xor rax, rbx     ; 1 where they differ       -> flip bits
not rax          ; flip every bit
test rax, rbx    ; like and, but only sets flags (ZF=1 if no common bits)
```

For example, with 4-bit values:

```
        1100           1100           1100
  and   1010     or    1010     xor   1010
      = 1000         = 1110         = 0110
```

A **mask** is a constant whose 1 bits select the bits you care about. Here is a
useful one. Memory is managed in **pages** of 4096 bytes, and 4096 = 2¹², so an
address splits cleanly in two: the high bits are the page number, and the low 12 bits
(mask `0xFFF`) are the offset inside the page:

```
v & ~0xFFF           the start of v's page         (round down)
(v + 0xFFF) & ~0xFFF the next page boundary ≥ v    (round up)
v & 0xFFF            the offset within the page
```

`~0xFFF` is the mask with every bit set *except* the low 12, so `and` with it clears
the offset and keeps the page number.

## Lesson: two classics

- `xor eax, eax` is the standard way to zero a register: anything xor itself is 0.
  It's shorter than `mov eax, 0`, and CPUs recognise it as a "zeroing idiom". Unlike
  `mov`, it **changes the flags**.
- Immediates are at most 32 bits, **sign-extended**: `and rax, ~0xFFF` works because
  ~0xFFF is −4096, whose 64-bit sign extension is `0xFFFF_FFFF_FFFF_F000`. But
  `xor rax, 0x8000_0000_0000_0000` can't be encoded. NASM warns you, and you load the
  constant into a register first.

## Gate

On entry `rdi` = v (below 2⁶²). The tests put garbage in r9 first.

| Register | Must hold |
|---|---|
| `rax` | v rounded down to a multiple of 4096 |
| `rbx` | v with its low 12 bits set |
| `rcx` | v with bit 63 flipped |
| `rdx` | every bit of v flipped |
| `r8` | v rounded **up** to a multiple of 4096 |
| `r9` | 0, using the xor idiom |
| `r10` | 1 if v is a multiple of 8, else 0 (use `test`) |

`rdi` must be unchanged. Constraints: at most 22 instructions; must use `and`, `or`,
`xor`, `not` and `test`; no shifts or multiplication.
