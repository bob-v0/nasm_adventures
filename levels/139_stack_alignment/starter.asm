; Level 139 — Stack Alignment
;
; sum_squares(rdi = n, rsi = k) = sum of (i*k)^2 for i = 1..n
; Call ring_square(x) for each square; rsp must be 16-byte aligned at each call.

extern ring_square
global sum_squares

section .text
sum_squares:
    ; TODO
    ret
