; Level 63 — Packed Floats (reference)

global ring_dot

section .text
ring_dot:                       ; rdi = a, rsi = b, rdx = n
    xorps xmm0, xmm0            ; four accumulators, four lanes each
    xorps xmm1, xmm1
    xorps xmm2, xmm2
    xorps xmm3, xmm3
    mov rcx, rdx
    shr rcx, 4                  ; blocks of 16
    jz .reduce
.block:
    movaps xmm4, [rdi]
    mulps xmm4, [rsi]
    addps xmm0, xmm4
    movaps xmm5, [rdi + 16]
    mulps xmm5, [rsi + 16]
    addps xmm1, xmm5
    movaps xmm6, [rdi + 32]
    mulps xmm6, [rsi + 32]
    addps xmm2, xmm6
    movaps xmm7, [rdi + 48]
    mulps xmm7, [rsi + 48]
    addps xmm3, xmm7
    add rdi, 64
    add rsi, 64
    dec rcx
    jnz .block
.reduce:
    addps xmm0, xmm1
    addps xmm2, xmm3
    addps xmm0, xmm2            ; one register, four partial sums
    movhlps xmm1, xmm0
    addps xmm0, xmm1            ; lanes 0+2, 1+3
    movaps xmm1, xmm0
    shufps xmm1, xmm1, 1
    addss xmm0, xmm1            ; the total, in lane 0
    and edx, 15
    jz .done
.tail:
    movss xmm1, [rdi]
    mulss xmm1, [rsi]
    addss xmm0, xmm1
    add rdi, 4
    add rsi, 4
    dec edx
    jnz .tail
.done:
    ret
