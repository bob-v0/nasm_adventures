; Level 65 — Masks & Compares (reference)

global ring_memchr

section .text
ring_memchr:                    ; rdi = buf, esi = byte, rdx = n
    movd xmm1, esi
    pxor xmm2, xmm2
    pshufb xmm1, xmm2           ; the byte in all 16 lanes
    xor eax, eax                ; offset
    mov rcx, rdx
    and rcx, -16                ; the bytes in whole blocks
.block:
    cmp rax, rcx
    jae .tail
    movdqu xmm0, [rdi + rax]
    pcmpeqb xmm0, xmm1          ; 0xFF where it matches
    pmovmskb r8d, xmm0          ; bit i = byte i matched
    test r8d, r8d
    jnz .hit
    add rax, 16
    jmp .block
.hit:
    tzcnt r8d, r8d              ; the first match in the block
    add rax, r8
    ret
.tail:
    cmp rax, rdx
    jae .none
    cmp [rdi + rax], sil
    je .found
    inc rax
    jmp .tail
.none:
    mov rax, -1
.found:
    ret
