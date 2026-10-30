; Level 97 — Branch Prediction
;
; ring_sum_big(bytes, n): the sum of the bytes that are >= 128 (unsigned).
; On sorted data: fast. On random data: about 10 cycles per byte. Get random data
; under 3 cycles per byte.

global ring_sum_big

section .text
ring_sum_big:                   ; rdi = bytes, rsi = n
    xor eax, eax
    test rsi, rsi
    jz .done
.next:
    movzx ecx, byte [rdi]
    cmp ecx, 128
    jb .skip                    ; small: leave it out
    add rax, rcx
.skip:
    inc rdi
    dec rsi
    jnz .next
.done:
    ret
