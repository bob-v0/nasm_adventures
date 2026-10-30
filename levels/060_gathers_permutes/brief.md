# Level 60 — Gathers & Permutes

*Up to now every vector came from consecutive memory. Lookup tables don't work like
that: each lane wants a different address.*

## Lesson: gathers

AVX2's **gather** loads each lane from its own address. The address uses **VSIB**
addressing: a base register plus a *vector* of indexes, scaled:

```
vpgatherdd ymm0, [rcx + ymm1*4], ymm2     ; lane i: ymm0[i] = dword at rcx + 4·ymm1[i]
```

The third operand is the **mask**: only lanes whose mask element has its top bit set are
loaded (others keep their old value and can't fault). The gather **clears the mask** as
lanes complete, so it can be interrupted by a page fault and restarted where it was:
set it again (`vpcmpeqd ymm2, ymm2, ymm2`) before every gather. The mask, index and
destination must be three different registers. (`vpgatherdq`, `vpgatherqd`, `vgatherdps`
... for the other sizes.)

A gather is not faster memory: it's 8 loads, and the load ports do them one by one. It
wins when the alternative is 8 scalar loads *plus* 8 inserts to get the values into a
vector. AVX-512 adds **scatters**, the stores.

## Lesson: lanes in AVX2

Most AVX2 shuffles (`vpshufb`, `vpshufd`, `vpunpck*`, `vpalignr`) work on the two 128-bit
halves of a ymm register **separately**: they are two SSE shuffles side by side. Moving
data between the halves needs a **lane-crossing** instruction:

| instruction | effect |
|---|---|
| `vpermd ymm0, ymm_idx, ymm1` | lane i = lane idx[i] of ymm1: any dword permutation (`vpermps` for floats) |
| `vpermq ymm0, ymm1, imm8` | qwords, chosen by 2-bit fields of the immediate |
| `vperm2i128 ymm0, ymm1, ymm2, imm8` | pick each 128-bit half from ymm1 or ymm2 |
| `vinserti128` / `vextracti128` | put / take a 128-bit half |
| `vpbroadcastd ymm0, xmm1` | dword 0 everywhere |

Lane-crossing shuffles take 3 cycles instead of 1. Note the operand order of `vpermd`:
the indexes come *first*.

## Lesson: widening

`vpmovzxbd ymm1, [rdi]` reads 8 bytes and zero-extends each to a dword (`bw`, `bq`,
`wd`, `dq` and the sign-extending `vpmovsx*` too). Indexes stored as bytes become a
vector of dword indexes for the gather.

## Gate

`ring_blit_mirrored(src, dst, n, palette)` with `vpgatherdd` and `vpermd`, within
**0.8 cycles per pixel**.
