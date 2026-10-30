; Level 93 — Performance Cliff
;
; ring_smooth(in, out, n): converts n samples (doubles) to the instrument's unit
; (x 1e-300) and smooths them with a low-pass filter:
;     y = y / 2 + in[i] * 1e-300;  out[i] = y      (y starts at 0)
; The recordings are 500 loud samples, then a quiet tail. 500 samples take about
; 4 400 cycles; 3000 samples take about 520 000: 20x more per sample.
;
; 1. Find an input size that falls off the cliff:   ;! witness n = N
; 2. Fix it (the output may differ only in values too tiny to matter: below 1e-300).

global ring_smooth

section .text
ring_smooth:                    ; rdi = in, rsi = out, rdx = n
    mov rax, 0x3FE0000000000000 ; 0.5
    movq xmm1, rax
    mov rax, 0x01A56E1FC2F8F359 ; 1e-300
    movq xmm2, rax
    xorpd xmm0, xmm0            ; y
    test rdx, rdx
    jz .done
.next:
    movsd xmm3, [rdi]
    mulsd xmm3, xmm2            ; to the instrument's unit
    mulsd xmm0, xmm1
    addsd xmm0, xmm3
    movsd [rsi], xmm0
    add rdi, 8
    add rsi, 8
    dec rdx
    jnz .next
.done:
    ret
