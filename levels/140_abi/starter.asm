; Level 140 — System V ABI
;
; poly(rdi = x, rsi = a, rdx = b, rcx = c) = a*x*x + b*x + c
; Get x*x from ring_square(x), called exactly once. It destroys rax, rcx, rdx,
; rsi, rdi, r8-r11. Your caller expects rbx, rbp, r12-r15 unchanged.

extern ring_square
global poly

section .text
poly:
    ; TODO
    ret
