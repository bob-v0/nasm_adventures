; Level 64 — Tail Overrun (reference)
;! witness n = 4

global ring_strlen

section .text
ring_strlen:                    ; rdi = s
    mov rax, rdi
    and rax, -16                ; the aligned block holding s: never crosses a page
    mov ecx, edi
    and ecx, 15                 ; how far into it s starts
    pxor xmm1, xmm1             ; zeros, to compare with
    movdqa xmm0, [rax]
    pcmpeqb xmm0, xmm1
    pmovmskb edx, xmm0
    shr edx, cl                 ; forget the bytes before s
    test edx, edx
    jnz .first
.block:
    add rax, 16
    movdqa xmm0, [rax]          ; 16 bytes of the string
    pcmpeqb xmm0, xmm1
    pmovmskb edx, xmm0          ; bit i: byte i is the NUL
    test edx, edx
    jz .block
    tzcnt edx, edx
    add rax, rdx
    sub rax, rdi                ; the NUL's address − s
    ret
.first:
    tzcnt eax, edx              ; the NUL is in the first block
    ret
