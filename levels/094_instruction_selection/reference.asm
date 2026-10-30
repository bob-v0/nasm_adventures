; Level 94 — Instruction Selection (reference)
;
; - movzx: a full-register load, no dependency on the old rax
; - b % 10 without div: q = (b * 205) >> 11 is exactly b / 10 for b < 1024, and
;   b - 10q = b - (q*8 + q*2): an imul and two lea instead of a 26-cycle division
; - dec + jnz fuse into one uop; loop is 7 of them

global ring_digit_sum

section .text
ring_digit_sum:                 ; rdi = bytes, rsi = n
    xor eax, eax
    test rsi, rsi
    jz .done
.next:
    movzx ecx, byte [rdi]
    imul edx, ecx, 205
    shr edx, 11                 ; edx = b / 10
    lea edx, [rdx + rdx*4]      ; 5q
    add edx, edx                ; 10q
    sub ecx, edx                ; b % 10
    add eax, ecx
    inc rdi
    dec rsi
    jnz .next
.done:
    ret
