; Level 61 — FMA
;
; ring_exp(in, out, n): out[i] = e^in[i] for n floats, −87.3 ≤ in[i] ≤ 88.7.
; Every result within 2 ULPs of the correctly rounded value (2 floats away). 1 cycle
; per element at most; this CPU has AVX2 and FMA, and the solution must use FMA.
; Don't write past out[n − 1]. vzeroupper before you return.
;
; The plan (see the brief):
;   k = round(x / ln 2),  r = x − k·ln 2               (|r| ≤ 0.35)
;   p = 1 + r + r²/2! + r³/3! + ... + r⁷/7!            (Horner, with FMA)
;   e^x = p · 2^k                                      (add k to p's exponent)

global ring_exp

section .rodata
align 32
log2e_8: times 8 dd 1.44269504     ; 1 / ln 2
ln2hi_8: times 8 dd 0.693359375    ; ln 2 = ln2hi + ln2lo
ln2lo_8: times 8 dd -2.12194440e-4
c7_8:    times 8 dd 1.98412698e-4  ; 1/7!
c6_8:    times 8 dd 1.38888889e-3  ; 1/6!
c5_8:    times 8 dd 8.33333333e-3  ; 1/5!
c4_8:    times 8 dd 4.16666667e-2  ; 1/4!
c3_8:    times 8 dd 1.66666667e-1  ; 1/3!
c2_8:    times 8 dd 0.5
one_8:   times 8 dd 1.0

section .text
ring_exp:                       ; rdi = in, rsi = out, rdx = n
    ; TODO
    ret
