; Level 98 — Pipelines
;
; ring_sum(values, n): the sum of n doubles, returned in xmm0.
; Correct, and on the game's CPU about 4.5 cycles per value. Get it under 2.

global ring_sum

section .text
ring_sum:                       ; rdi = values, rsi = n
    xorpd xmm0, xmm0
    test rsi, rsi
    jz .done
.next:
    addsd xmm0, [rdi]
    add rdi, 8
    dec rsi
    jnz .next
.done:
    ret
