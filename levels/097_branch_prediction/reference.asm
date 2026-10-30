; Level 97 — Branch Prediction (reference)
;
; No branch depends on the data: cmov picks the value or 0, and the only branch left
; is the loop's, which the predictor gets right every time but the last.

global ring_sum_big

section .text
ring_sum_big:                   ; rdi = bytes, rsi = n
    xor eax, eax
    xor edx, edx                ; a zero to choose instead
    test rsi, rsi
    jz .done
.next:
    movzx ecx, byte [rdi]
    cmp ecx, 128
    cmovb ecx, edx              ; small: count it as 0
    add rax, rcx
    inc rdi
    dec rsi
    jnz .next
.done:
    ret
