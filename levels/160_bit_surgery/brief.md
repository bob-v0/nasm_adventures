# Level 160 — Bit Surgery

*A set of 256 things fits in 32 bytes. Operating on it takes single instructions.*

## Lesson: bit strings

A **bitset** stores a set of small numbers using one bit per possible member: bit i
is 1 if i is in the set. 256 possible members fit in four qwords. Bit i lives in
qword i / 64, at position i % 64:

```
            qword 0       qword 1       qword 2       qword 3
offset      +0            +8            +16           +24
holds bits  0 .. 63       64 .. 127     128 .. 191    192 .. 255

bit 200:  200 / 64 = 3 (qword 3, at +24),  200 % 64 = 8 (bit 8 of it)
```

Four instructions test and change single bits. Each copies the bit's old value into
CF first:

```
bt  rax, 5        ; CF = bit 5 of rax           (test)
bts rax, 5        ; CF = old bit, then set it   (test and set)
btr rax, 5        ; ... and reset (clear) it
btc rax, 5        ; ... and complement (flip) it
```

With a **memory** operand and a **register** offset, these treat memory as one long
bit string: `bts [setA], rdi` with rdi = 200 sets bit 8 of the qword at setA + 24.
The CPU does the division for you. (With an immediate offset it only reaches bits
0–63 of the operand.)

## Lesson: counting and scanning

```
popcnt rax, rbx   ; number of 1 bits
tzcnt  rax, rbx   ; index of the lowest 1 bit (64 if rbx = 0, and CF = 1)
lzcnt  rax, rbx   ; number of leading 0 bits (64 if rbx = 0)
bsf    rax, rbx   ; index of the lowest 1 bit (ZF = 1 and rax undefined if rbx = 0)
bsr    rax, rbx   ; index of the highest 1 bit (same caveat)
```

`bsf`/`bsr` are the originals. `tzcnt`/`lzcnt` came later and define the zero case,
which avoids a classic bug. Scanning four qwords takes a small loop or four unrolled
steps. You know enough jumps for either.

## Gate

The game provides `setA` and `setB` (256 bits each). On entry `rdi`, `rsi`, `rdx` are
bit indexes 0–255.

1. Set bit `rdi` in setA, and clear bit `rsi` in setB.
2. Then:

| Register | Must hold |
|---|---|
| `rax` | the number of elements in setA |
| `rbx` | the index of the lowest set bit of setA (it is never empty after step 1) |
| `rcx` | 1 if bit `rdx` of setB is set, else 0 |
| `r8` | the index of the highest set bit of setB, or −1 if setB is empty |

The tests check both sets in memory too. The inputs must be unchanged. Constraints: at
most 60 instructions; must use `bts`, `btr`, `bt` and `popcnt`.
