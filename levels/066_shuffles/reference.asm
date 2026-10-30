; Level 66 — Shuffles (reference)

global ring_reverse

section .rodata
align 16
reverse: db 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0

section .text
ring_reverse:                   ; rdi = buf, rsi = n
    lea rdx, [rdi + rsi]        ; one past the end
    movdqa xmm7, [rel reverse]
.block:
    mov rax, rdx
    sub rax, rdi
    cmp rax, 32
    jb .middle
    movdqu xmm0, [rdi]
    movdqu xmm1, [rdx - 16]
    pshufb xmm0, xmm7
    pshufb xmm1, xmm7
    movdqu [rdi], xmm1
    movdqu [rdx - 16], xmm0
    add rdi, 16
    sub rdx, 16
    jmp .block
.middle:
    dec rdx                     ; the last byte
.swap:
    cmp rdi, rdx
    jae .done
    movzx eax, byte [rdi]
    movzx ecx, byte [rdx]
    mov [rdi], cl
    mov [rdx], al
    inc rdi
    dec rdx
    jmp .swap
.done:
    ret
