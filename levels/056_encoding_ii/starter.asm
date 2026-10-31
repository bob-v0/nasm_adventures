; Level 56 — Encoding II
;
; db lines only again: 64-bit registers, prefixes, SSE and AVX. The first one is done.
; (Any valid encoding counts.) The tables are in the brief.

    db 0x48, 0xB8, 0x88, 0x77, 0x66, 0x55, 0x44, 0x33, 0x22, 0x11; mov rax, 0x1122334455667788
    ; TODO                                      ; mov r9, rax
    ; TODO                                      ; lea r10, [r9+8]
    ; TODO                                      ; sub r10, rax
    ; TODO                                      ; push r9
    ; TODO                                      ; pop r11
    ; TODO                                      ; mov r12d, 0x7F
    ; TODO                                      ; mov [rsp-16], r12
    ; TODO                                      ; movzx r13d, byte [rsp-16]
    ; TODO                                      ; inc r13
    ; TODO                                      ; mov ax, 0x1234
    ; TODO                                      ; movsx rdx, word [rsp-16]
    ; TODO                                      ; lock xadd [rsp-16], r12d
    ; TODO                                      ; mov r14, [rsp-16]
    ; TODO                                      ; mov dil, 7
    ; TODO                                      ; pcmpeqd xmm0, xmm0
    ; TODO                                      ; movdqu [rsp-32], xmm0
    ; TODO                                      ; pxor xmm8, xmm8
    ; TODO                                      ; psubd xmm8, xmm0
    ; TODO                                      ; cvtsi2sd xmm1, r12
    ; TODO                                      ; addsd xmm1, xmm1
    ; TODO                                      ; cvttsd2si r8, xmm1
    ; TODO                                      ; vpaddd ymm2, ymm0, ymm0
    ; TODO                                      ; vpaddd ymm9, ymm2, ymm8
    ; TODO                                      ; vmovd esi, xmm9
    ; TODO                                      ; vzeroupper
