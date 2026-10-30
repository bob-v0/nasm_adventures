; Level 69 — SSE Scalar
;
; ring_dtoa(x, buf): write the double x as text with three decimals into buf, and
; return its length in rax:
;
;     3.25 -> "3.250"     -12.5 -> "-12.500"     0.1 -> "0.100"
;     NaN  -> "nan"       ±infinity -> "inf" / "-inf"
;
; The rule: a '-' when x's sign bit is set (so -0.0 -> "-0.000"); then
; n = |x| × 1000 rounded to an integer the way MXCSR's rounding mode says (callers
; usually leave it at "to nearest, ties to even", but not always), printed as
; n / 1000, '.', and n % 1000 in exactly three digits. |x| is below 10^12.

global ring_dtoa

section .rodata
thousand: dq 1000.0

section .text
ring_dtoa:                      ; xmm0 = x, rdi = buf
    ; TODO
    xor eax, eax
    ret
