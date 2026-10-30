; Level 67 — SIMD Integers
;
; ring_brighten(pixels, n, amount): add amount (0..255) to each of the n grey pixels
; (bytes), clamping at 255 (white stays white). Don't touch anything after pixel n − 1.
;
; This works, one pixel at a time: about 2 cycles per pixel. The budget is 0.4: do 16
; at a time with SSE.

global ring_brighten

section .text
ring_brighten:                  ; rdi = pixels, rsi = n, edx = amount
    test rsi, rsi
    jz .done
    mov ecx, 255
.next:
    movzx eax, byte [rdi]
    add eax, edx
    cmp eax, ecx
    cmova eax, ecx              ; clamp
    mov [rdi], al
    inc rdi
    dec rsi
    jnz .next
.done:
    ret
