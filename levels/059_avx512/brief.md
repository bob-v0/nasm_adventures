# Level 59 — AVX-512

*Twice as wide again, and the bigger change isn't the width: every instruction can be
told which lanes to work on.*

## Lesson: zmm and EVEX

AVX-512 (servers since 2017, Ice Lake laptops, AMD Zen 4) has **32** registers of 512
bits, **zmm0–zmm31**. As before, ymm and xmm are their low parts, and xmm16–31 and
ymm16–31 exist too. The instructions use a new encoding, **EVEX**, which adds what AVX
lacked:

- **mask registers** k1–k7: 64-bit registers holding one bit per lane;
- **masking** for (almost) every instruction: `vpaddd zmm0{k1}, zmm1, zmm2` only writes
  the lanes whose bit in k1 is set. The others keep their value (**merging**), or become
  0 if you write `{k1}{z}` (**zeroing**);
- **broadcast** memory operands: `vpaddd zmm0, zmm1, [rdi]{1to16}` adds one dword from
  memory to all 16 lanes;
- integer moves that name a lane size, so the mask knows what a lane is: `vmovdqu32`,
  `vmovdqu8`, `vmovdqa64`.

Merging and zeroing, on 4 lanes for short:

```
k1                     =  0    1    1    0
zmm1 + zmm2            = 11   22   33   44
zmm0 before            =  7    7    7    7
vpaddd zmm0{k1}, ...   =  7   22   33    7      (merging)
vpaddd zmm0{k1}{z},... =  0   22   33    0      (zeroing)
```

AVX-512 is a family: F (foundation), BW (bytes and words), DQ, VL (the masked 128- and
256-bit forms), CD, VBMI, ... each its own cpuid bit (leaf 7). This level's CPU has
F, BW, DQ, VL, CD, VBMI, VPOPCNTDQ and BITALG.

## Lesson: compares into masks

AVX-512 compares write **mask registers**, not vectors. `vpcmpgtd k1, zmm0, zmm1` sets
bit i of k1 if dword i of zmm0 > dword i of zmm1. (`vpcmpd k1, zmm0, zmm1, imm` covers
all eight predicates; `vpcmpud` is unsigned.)

Masks have their own instructions: `kmovw eax, k1` / `kmovw k1, eax`, `kandw`, `korw`,
`knotw`, and `kortestw` (sets ZF if the OR is all zero). A mask is level 65's movemask,
without the movemask.

## Lesson: masked memory never faults

A masked load or store **doesn't touch** masked-off lanes. They can't fault, even when
they'd fall on an unmapped page. So the tail of an array needs no scalar loop and no
overreading tricks (level 64): build a mask of the remaining n % 16 lanes
(`bzhi eax, eax, esi` keeps the low esi bits of eax) and run the same code once more
with it.

## Lesson: compress

`vpcompressd [rcx]{k1}, zmm0` stores the lanes selected by k1 **one after the other**:
lanes 2, 5 and 11 become three consecutive dwords at rcx. It's a filter in one
instruction. (`vpexpandd` is the inverse.) Before AVX-512, the same job took a 256-entry
table of shuffle patterns.

## Gate

`ring_filter(in, n, threshold, out)` copies the elements of in[0 .. n−1] (signed dwords)
that are greater than threshold to out, in order and packed together, and returns how
many. Nothing else in out may change.

- in ends right before an unmapped page: don't read past in[n − 1].
- Budget: **0.4 cycles per element**, plus a small fixed allowance.
