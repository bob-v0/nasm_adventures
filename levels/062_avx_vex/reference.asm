; Level 62 — AVX & VEX (reference)

global ring_saxpy

AVX     equ 1 << 28             ; cpuid(1).ecx
OSXSAVE equ 1 << 27

section .text
ring_saxpy:                     ; rdi = y, rsi = x, rdx = n, xmm0 = a
    mov r8, rdx
    mov r9, rbx                 ; cpuid writes ebx (callee-saved)
    mov eax, 1
    cpuid
    mov rbx, r9
    and ecx, AVX | OSXSAVE
    cmp ecx, AVX | OSXSAVE
    jne .sse
    xor ecx, ecx
    xgetbv                      ; XCR0: which register state the OS saves
    and eax, 6
    cmp eax, 6                  ; SSE and AVX (ymm) state
    jne .sse
.avx:
    vbroadcastss ymm1, xmm0     ; a in all 8 lanes
    mov rcx, r8
    shr rcx, 3
    jz .avx_done
.avx_block:
    vmulps ymm2, ymm1, [rsi]
    vaddps ymm2, ymm2, [rdi]
    vmovups [rdi], ymm2
    add rsi, 32
    add rdi, 32
    dec rcx
    jnz .avx_block
.avx_done:
    vzeroupper
    and r8d, 7
    jmp .tail
.sse:
    movaps xmm1, xmm0
    shufps xmm1, xmm1, 0        ; a in all 4 lanes
    mov rcx, r8
    shr rcx, 2
    jz .sse_done
.sse_block:
    movups xmm2, [rsi]
    mulps xmm2, xmm1
    movups xmm3, [rdi]
    addps xmm2, xmm3
    movups [rdi], xmm2
    add rsi, 16
    add rdi, 16
    dec rcx
    jnz .sse_block
.sse_done:
    and r8d, 3
.tail:
    test r8d, r8d
    jz .done
.one:
    movss xmm2, [rsi]
    mulss xmm2, xmm0
    addss xmm2, [rdi]
    movss [rdi], xmm2
    add rsi, 4
    add rdi, 4
    dec r8d
    jnz .one
.done:
    ret
