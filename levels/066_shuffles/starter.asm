; Level 66 — Shuffles
;
; ring_reverse(buf, n): reverse the n bytes at buf, in place. Don't touch anything
; after byte n − 1.
;
; This works, two bytes at a time from both ends: about 1.5 cycles per byte. The
; budget is 0.3: reverse 16 bytes at a time with pshufb.

global ring_reverse

section .text
ring_reverse:                   ; rdi = buf, rsi = n
    lea rdx, [rdi + rsi - 1]    ; the last byte
.next:
    cmp rdi, rdx
    jae .done
    movzx eax, byte [rdi]
    movzx ecx, byte [rdx]
    mov [rdi], cl
    mov [rdx], al
    inc rdi
    dec rdx
    jmp .next
.done:
    ret
