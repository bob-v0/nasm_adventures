# Level 93 — Bug: Performance Cliff ◆◆

*The code is fine. The algorithm is fine. One input is twenty times slower per element
than another of the same kind. Performance bugs hide in the data.*

## Symptoms

`ring_smooth` converts audio samples to the instrument's unit (× 1e-300) and runs a
simple low-pass filter over them. A 500-sample recording: about 9 cycles per sample.
3000 samples: about 170 per sample. Same loop, same instructions, and nothing in the
code depends on the size.

## Background: cliffs

A **performance cliff** is a sudden drop in speed, caused by a condition the hardware
handles on a slow path. The classics:

- **denormal numbers**: tiny floating-point values, handled by microcode;
- **4K aliasing**: a load and an earlier store whose addresses differ by a multiple of
  4096 look like a conflict, and the load waits (array sizes that are powers of two
  trigger it);
- **split accesses**: a load or store straddling two 64-byte lines, or worse, two pages;
- **cache associativity**: power-of-two strides that use only a few cache sets (level 96).

The game's report counts every one of them.

## Background: denormals

A normal double is `1.xxx × 2^e` with `e ≥ −1022`. Below about `2.2e−308`, IEEE 754
carries on with **denormal** (or subnormal) numbers, `0.xxx × 2^−1022`, so that values
shrink gradually towards zero instead of dropping straight to it:

```
0 ...... 4.9e-324 ......... 2.2e-308 ............... 1.0
|<-------- denormal ------->|<-------- normal --------- ...
   slow: ~100-cycle assist          fast path
```

Most CPUs don't handle denormals in the fast path: an operation that produces or
consumes one takes a **microcode assist**, around 100 cycles. Audio processing is famous
for this: when the music fades out, filter state decays into denormals and the CPU load
jumps.

The SSE control register **MXCSR** has two switches for programs that don't need this
gradual underflow:

- **FTZ** (flush to zero, bit 15): denormal results become 0;
- **DAZ** (denormals are zero, bit 6): denormal inputs are read as 0.

`stmxcsr [m32]` / `ldmxcsr [m32]` read and write it. (Compilers set both with
`-ffast-math`. Some libraries and games do it at startup.)

## Gate

1. Add a witness: an input size `n` (1–4096) at which the **original** blows its budget
   of 12 cycles per sample: `;! witness n = N`.
2. Fix it, changing at most **6 lines**. Outputs may differ from the exact ones only in
   values below 1e-300.
