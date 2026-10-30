; Level 60 — Gathers & Permutes
;
; ring_blit_mirrored(src, dst, n, palette): draw a sprite row mirrored. src holds n
; palette indexes (bytes); palette holds 256 colours (dwords). Pixel i of the sprite
; becomes the colour palette[src[i]], written at dst[n − 1 − i]. Don't write outside
; dst[0 .. n−1].
;
; This works, one pixel at a time: about 1.3 cycles per pixel. The budget is 0.8
; (this CPU has AVX2): look 8 colours up at once with vpgatherdd, and turn them
; around with vpermd.

global ring_blit_mirrored

section .text
ring_blit_mirrored:             ; rdi = src, rsi = dst, rdx = n, rcx = palette
    lea r8, [rsi + rdx*4]       ; one past dst's end: the mirrored writes go downwards
    test rdx, rdx
    jz .done
.one:
    movzx eax, byte [rdi]
    mov eax, [rcx + rax*4]
    sub r8, 4
    mov [r8], eax
    inc rdi
    dec rdx
    jnz .one
.done:
    ret
