# Level 60 — Gathers & Permutes

*Up to now every vector came from consecutive memory. Lookup tables don't work like
that: each lane wants a different address.*

## Lesson: gathers

AVX2's **gather** loads each lane from its own address. The address uses **VSIB**
addressing ("vector SIB"): a base register plus a *vector* of indexes, scaled:

```
vpgatherdd ymm0, [rcx + ymm1*4], ymm2     ; lane i: ymm0[i] = dword at rcx + 4·ymm1[i]
```

The third operand is the **mask**. Only lanes whose mask element has its top bit set are
loaded; the others keep their old value and can't fault.

Two rules that trip everyone up:

- The gather **clears the mask** as lanes complete. (That way a page fault halfway can
  restart where it stopped.) So set the mask again before every gather:
  `vpcmpeqd ymm2, ymm2, ymm2` makes it all ones.
- The mask, index and destination must be three different registers.

Other sizes: `vpgatherdq`, `vpgatherqd`, `vgatherdps`, ...

A gather is not faster memory: it's 8 loads, and the load ports do them one by one. It
wins when the alternative is 8 scalar loads *plus* 8 inserts to get the values into a
vector. (AVX-512 adds **scatters**, the matching stores.)

## Lesson: lanes in AVX2

Most AVX2 shuffles (`vpshufb`, `vpshufd`, `vpunpck*`, `vpalignr`) work on the two 128-bit
halves of a ymm register **separately**. They are two SSE shuffles side by side, and no
byte crosses the middle:

```
ymm0:  [ dword 7  6  5  4 ][ dword 3  2  1  0 ]
           high 128 bits       low 128 bits

vpshufd, vpshufb:  each half shuffled on its own; nothing crosses the middle
vpermd:            any dword can go to any lane
```

Moving data between the halves needs a **lane-crossing** instruction:

| instruction | effect |
|---|---|
| `vpermd ymm0, ymm_idx, ymm1` | lane i = lane idx[i] of ymm1: any dword permutation (`vpermps` for floats) |
| `vpermq ymm0, ymm1, imm8` | qwords, chosen by 2-bit fields of the immediate |
| `vperm2i128 ymm0, ymm1, ymm2, imm8` | pick each 128-bit half from ymm1 or ymm2 |
| `vinserti128` / `vextracti128` | put / take a 128-bit half |
| `vpbroadcastd ymm0, xmm1` | dword 0 everywhere |

Lane-crossing shuffles take 3 cycles instead of 1. Mind the operand order of `vpermd`:
the indexes come *first*.

## Lesson: widening

`vpmovzxbd ymm1, [rdi]` reads 8 bytes and zero-extends each to a dword. (There are also
`bw`, `bq`, `wd`, `dq`, and the sign-extending `vpmovsx*`.) That's how indexes stored as
bytes become a vector of dword indexes for a gather.

## Gate

`ring_blit_mirrored(src, dst, n, palette)` draws a sprite row mirrored. src holds n
palette indexes (bytes); palette holds 256 colours (dwords). Pixel i becomes
palette[src[i]], written at dst[n − 1 − i]. Nothing outside dst[0 .. n−1] may change.

- Use `vpgatherdd` and `vpermd` (the tests check both appear).
- Budget: **0.8 cycles per pixel**, plus a small fixed allowance. The CPU has AVX2.
