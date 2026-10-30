; Level 71 — IEEE 754
;
; ring_dtoi(bits): rdi holds the 64 bits of a double. Return in rax what
; cvttsd2si rax, xmm0 would: the value truncated toward zero, as a signed
; 64-bit integer; and 0x8000000000000000 (the "integer indefinite") when it
; doesn't fit, or it's an infinity or a NaN.
;
; With integer instructions only: no x87, SSE or AVX.
;
;   bit  63      62 ........ 52   51 ................ 0
;       sign      exponent e       fraction f
;
;   e = 0:          zero or denormal: ±0.f × 2^-1022
;   e = 1..2046:    normal:           ±1.f × 2^(e - 1023)
;   e = 2047:       f = 0: ±infinity, otherwise NaN

global ring_dtoi

section .text
ring_dtoi:                      ; rdi = the bits
    ; TODO
    xor eax, eax
    ret
