; Level 94 — Instruction Selection
;
; ring_digit_sum(bytes, n): for each byte b (0..255), add up b % 10; return the total.
; Every instruction here is a reasonable choice for the job, and the loop takes about
; 30 cycles per byte on the game's CPU. Make it at least 2x faster (under 15 per byte);
; much better is possible.

global ring_digit_sum

section .text
ring_digit_sum:                 ; rdi = bytes, rsi = n
    push rbx
    xor ebx, ebx                ; the total
    mov rcx, rsi
    jrcxz .done
.next:
    push rcx
    mov al, [rdi]               ; the byte
    xor edx, edx
    and eax, 0xFF
    mov ecx, 10
    div ecx                     ; edx = b % 10
    add ebx, edx
    inc rdi
    pop rcx
    loop .next
.done:
    mov eax, ebx
    pop rbx
    ret
