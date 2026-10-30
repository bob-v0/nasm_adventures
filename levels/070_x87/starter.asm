; Level 70 — x87 (Museum)
;
; ring_rotate(x, y, angle): rotate the point (x, y) by angle radians around the origin:
;     x' = x·cos(angle) − y·sin(angle)
;     y' = x·sin(angle) + y·cos(angle)
; Return x' in xmm0, y' in xmm1, and in rax the length of (x', y') rounded DOWN to an
; integer: floor(sqrt(x'² + y'²)).
;
; All the arithmetic on the x87 FPU (fsincos, fsqrt, fmul, ...); xmm registers only to
; move the values in and out. Round down by switching the FPU's rounding mode with
; fldcw, and put the control word back before you return. Leave the x87 stack empty.

global ring_rotate

section .text
ring_rotate:                    ; xmm0 = x, xmm1 = y, xmm2 = angle (doubles)
    ; TODO
    xor eax, eax
    ret
