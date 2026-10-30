; Level 60 — Gathers & Permutes (reference)

global ring_blit_mirrored

section .rodata
align 32
backwards: dd 7, 6, 5, 4, 3, 2, 1, 0

section .text
ring_blit_mirrored:             ; rdi = src, rsi = dst, rdx = n, rcx = palette
    lea r8, [rsi + rdx*4]       ; one past dst's end: the mirrored writes go downwards
    vmovdqa ymm3, [rel backwards]
    mov r9, rdx
    shr r9, 3
    jz .tail
.block:
    vpmovzxbd ymm1, [rdi]       ; 8 palette indexes, as dwords
    vpcmpeqd ymm2, ymm2, ymm2   ; gather all 8 lanes
    vpgatherdd ymm0, [rcx + ymm1*4], ymm2   ; 8 colours
    vpermd ymm0, ymm3, ymm0     ; in reverse order
    sub r8, 32
    vmovdqu [r8], ymm0
    add rdi, 8
    dec r9
    jnz .block
.tail:
    and edx, 7
    jz .done
.one:
    movzx eax, byte [rdi]
    mov eax, [rcx + rax*4]
    sub r8, 4
    mov [r8], eax
    inc rdi
    dec edx
    jnz .one
.done:
    vzeroupper
    ret
