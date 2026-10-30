; Level 98 — Pipelines (reference)
;
; addsd takes 4 cycles, and each one needs the previous sum: one accumulator can't go
; faster than 4 cycles per value however many units are free. Four independent sums
; keep four additions in flight; they're combined at the end.

global ring_sum

section .text
ring_sum:                       ; rdi = values, rsi = n
    xorpd xmm0, xmm0
    xorpd xmm1, xmm1
    xorpd xmm2, xmm2
    xorpd xmm3, xmm3
    mov rcx, rsi
    shr rcx, 2                  ; groups of 4
    jz .rest
.four:
    addsd xmm0, [rdi]
    addsd xmm1, [rdi + 8]
    addsd xmm2, [rdi + 16]
    addsd xmm3, [rdi + 24]
    add rdi, 32
    dec rcx
    jnz .four
.rest:
    and esi, 3                  ; the last 0..3
    jz .combine
.one:
    addsd xmm0, [rdi]
    add rdi, 8
    dec esi
    jnz .one
.combine:
    addsd xmm0, xmm1
    addsd xmm2, xmm3
    addsd xmm0, xmm2
    ret
