; Level 59 — AVX-512 (reference)

global ring_filter

section .text
ring_filter:                    ; rdi = in, rsi = n, edx = threshold, rcx = out
    mov r8, rcx
    vpbroadcastd zmm1, edx      ; the threshold in all 16 lanes
    mov rax, rsi
    shr rax, 4
    jz .tail
.block:
    vmovdqu32 zmm0, [rdi]
    vpcmpgtd k1, zmm0, zmm1     ; bit i: in[i] > threshold
    vpcompressd [rcx]{k1}, zmm0 ; store just those, packed together
    kmovw r9d, k1
    popcnt r9d, r9d
    lea rcx, [rcx + r9*4]
    add rdi, 64
    dec rax
    jnz .block
.tail:
    and esi, 15
    jz .done
    mov eax, -1
    bzhi eax, eax, esi          ; the low n % 16 bits
    kmovw k2, eax
    vmovdqu32 zmm0{k2}{z}, [rdi]    ; masked off lanes aren't read: no overrun
    vpcmpgtd k1{k2}, zmm0, zmm1
    vpcompressd [rcx]{k1}, zmm0
    kmovw r9d, k1
    popcnt r9d, r9d
    lea rcx, [rcx + r9*4]
.done:
    mov rax, rcx
    sub rax, r8
    shr rax, 2                  ; how many were kept
    vzeroupper
    ret
