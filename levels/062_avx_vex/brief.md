# Level 62 — AVX & VEX

*Twice as wide, three operands, and not on every machine: the first time your program
has to ask the CPU what it is.*

## Lesson: AVX

AVX (2011) widens the sixteen xmm registers to 256 bits: **ymm0-ymm15**, whose low halves
are the xmm registers. A ymm register holds 8 floats, 4 doubles, or (with AVX2, 2013)
32 bytes for the integer instructions.

AVX instructions use a new encoding, **VEX**, and are spelled with a `v`:

```
addps   xmm0, xmm1          ; SSE: xmm0 = xmm0 + xmm1 (destroys an input)
vaddps  ymm0, ymm1, ymm2    ; AVX: three operands, inputs survive
vaddps  ymm0, ymm1, [rdi]   ; memory operands need no alignment (except vmovaps/vmovdqa)
vaddps  xmm0, xmm1, xmm2    ; 128-bit VEX forms exist too
```

## Lesson: the upper halves

A VEX instruction writing xmm0 **zeroes** bits 128-255 of ymm0. A legacy SSE instruction
writing xmm0 **leaves them alone**. To keep them, the CPU must track them, and mixing
legacy SSE with dirty upper halves costs: on older Intel CPUs a ~70-cycle state switch,
on newer ones a false dependency on every SSE instruction.

So the rule: **`vzeroupper`** (zero the upper halves of all ymm registers) after AVX code,
before returning or calling code that may use SSE. Compilers insert it everywhere. The
game checks it when your function returns.

## Lesson: asking the CPU

Not every x86-64 CPU has AVX. Running `vaddps` on one that doesn't is an **illegal
instruction**: SIGILL. Programs that want AVX ask first and pick a code path:

1. `cpuid` with eax = 1: ecx bit 28 = the CPU has AVX, bit 27 = **OSXSAVE**, the OS has
   enabled `xsave` and the `xgetbv` instruction. (Bit 12 is FMA, a separate feature,
   level 61. Leaf 7 has AVX2, ebx bit 5, and AVX-512.)
2. `xgetbv` with ecx = 0 returns **XCR0** in edx:eax: which register state the OS saves
   on a context switch. Bits 1 and 2 (SSE, AVX) both set means ymm registers survive
   being interrupted. A CPU with AVX under an OS that doesn't save ymm state can't use it.

`cpuid` writes eax, ebx, ecx and edx, and **rbx is callee-saved**.

Real programs do this once and store a function pointer (glibc's `memcpy` is chosen like
this at startup). The game runs your function on several CPUs: an old one without AVX,
one with AVX only (2011: no AVX2, no FMA), an AVX2 one, and an AVX-512 one.

## Gate

`ring_saxpy(y, x, n, a)`: y += a·x, under **0.42 cycles per element** on CPUs with AVX,
**0.8** without, and never an illegal instruction.
