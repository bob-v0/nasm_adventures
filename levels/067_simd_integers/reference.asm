; Level 67 — SIMD Integers (reference)

global ring_brighten

section .text
ring_brighten:                  ; rdi = pixels, rsi = n, edx = amount
    movd xmm1, edx
    pxor xmm2, xmm2
    pshufb xmm1, xmm2           ; the amount in all 16 bytes
    mov rcx, rsi
    shr rcx, 4                  ; whole blocks of 16
    jz .tail
.block:
    movdqu xmm0, [rdi]
    paddusb xmm0, xmm1          ; 16 saturating adds
    movdqu [rdi], xmm0
    add rdi, 16
    dec rcx
    jnz .block
.tail:
    and esi, 15
    jz .done
    mov ecx, 255
.pixel:
    movzx eax, byte [rdi]
    add eax, edx
    cmp eax, ecx
    cmova eax, ecx
    mov [rdi], al
    inc rdi
    dec esi
    jnz .pixel
.done:
    ret
