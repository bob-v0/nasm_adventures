; Level 61 — FMA (reference)

global ring_exp

section .rodata
align 32
lanes:  dd 0, 1, 2, 3, 4, 5, 6, 7

section .text
; exp of the 8 floats in ymm0 -> ymm0 (uses ymm1-ymm3)
%macro EXP8 0
    vmulps ymm1, ymm0, [rel log2e_8]
    vroundps ymm1, ymm1, 0              ; k = round(x / ln 2), as a float
    vfnmadd231ps ymm0, ymm1, [rel ln2hi_8]   ; r = x − k·ln2hi (exact)
    vfnmadd231ps ymm0, ymm1, [rel ln2lo_8]   ; r −= k·ln2lo: |r| ≤ ln2 / 2
    vmovaps ymm2, [rel c7_8]            ; Horner: p = ((c7·r + c6)·r + ...)·r + 1
    vfmadd213ps ymm2, ymm0, [rel c6_8]
    vfmadd213ps ymm2, ymm0, [rel c5_8]
    vfmadd213ps ymm2, ymm0, [rel c4_8]
    vfmadd213ps ymm2, ymm0, [rel c3_8]
    vfmadd213ps ymm2, ymm0, [rel c2_8]
    vfmadd213ps ymm2, ymm0, [rel one_8]
    vfmadd213ps ymm2, ymm0, [rel one_8]     ; p ≈ e^r
    vcvtps2dq ymm1, ymm1                ; k as an integer
    vpslld ymm1, ymm1, 23               ; ... in the exponent field
    vpaddd ymm0, ymm2, ymm1             ; p · 2^k
%endmacro

ring_exp:                       ; rdi = in, rsi = out, rdx = n
    mov rcx, rdx
    shr rcx, 3
    jz .tail
.block:
    vmovups ymm0, [rdi]
    EXP8
    vmovups [rsi], ymm0
    add rdi, 32
    add rsi, 32
    dec rcx
    jnz .block
.tail:
    and edx, 7
    jz .done
    vmovd xmm3, edx
    vpbroadcastd ymm3, xmm3
    vpcmpgtd ymm3, ymm3, [rel lanes]    ; lane i: −1 if i < n % 8
    vmaskmovps ymm0, ymm3, [rdi]        ; only those lanes are read...
    vmovdqu [rsp-40], ymm3              ; (keep the mask in the red zone)
    EXP8
    vmovdqu ymm3, [rsp-40]
    vmaskmovps [rsi], ymm3, ymm0        ; ...and written
.done:
    vzeroupper
    ret

section .rodata
align 32                        ; each constant in all 8 lanes
log2e_8: times 8 dd 1.44269504
ln2hi_8: times 8 dd 0.693359375    ; ln 2 = ln2hi + ln2lo; ln2hi has only 10 bits
ln2lo_8: times 8 dd -2.12194440e-4
c7_8:    times 8 dd 1.98412698e-4  ; 1/7!
c6_8:    times 8 dd 1.38888889e-3
c5_8:    times 8 dd 8.33333333e-3
c4_8:    times 8 dd 4.16666667e-2
c3_8:    times 8 dd 1.66666667e-1
c2_8:    times 8 dd 0.5
one_8:   times 8 dd 1.0
