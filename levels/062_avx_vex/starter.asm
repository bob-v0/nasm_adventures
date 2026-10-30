; Level 62 — AVX & VEX
;
; ring_saxpy(y, x, n, a): y[i] = y[i] + a·x[i] for n floats (a arrives in xmm0).
; The arrays have no particular alignment. Results within 1e−6 (relative to |y| + |a·x|).
;
; This SSE version runs on every x86-64 CPU: 4 floats per instruction, about 0.6
; cycles per element. On a CPU with AVX the budget is 0.42: use 8-float ymm registers
; there. But the game also runs your code on older CPUs, and on them an AVX
; instruction is an illegal instruction: check what the CPU has (cpuid, xgetbv) and
; pick the loop at run time. Leave the upper ymm halves clean when you return.

global ring_saxpy

section .text
ring_saxpy:                     ; rdi = y, rsi = x, rdx = n, xmm0 = a
    shufps xmm0, xmm0, 0        ; a in all 4 lanes
    mov rcx, rdx
    shr rcx, 2
    jz .tail
.block:
    movups xmm2, [rsi]
    mulps xmm2, xmm0
    movups xmm3, [rdi]
    addps xmm2, xmm3
    movups [rdi], xmm2
    add rsi, 16
    add rdi, 16
    dec rcx
    jnz .block
.tail:
    and edx, 3
    jz .done
.one:
    movss xmm2, [rsi]
    mulss xmm2, xmm0
    addss xmm2, [rdi]
    movss [rdi], xmm2
    add rsi, 4
    add rdi, 4
    dec edx
    jnz .one
.done:
    ret
