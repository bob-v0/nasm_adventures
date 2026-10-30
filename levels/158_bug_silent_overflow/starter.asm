; Level 158 — Bug: Silent Overflow
;
; Before allocating a buffer for `count` records of `size` bytes each, plus a
; 16-byte header, this routine checks that the total stays within LIMIT.
;
; On entry: rdi = count, rsi = size (both unsigned)
;   rax = total bytes = count * size + 16, or -1 if that exceeds LIMIT
;
; An attacker can make this check pass for a request of exabytes.
; 1. Prove it: add a witness line with such an input, e.g.
;        ;! witness rdi = 123, rsi = 456
; 2. Fix it, changing at most 4 lines.

LIMIT equ 1 << 20

    mov rax, rdi
    imul rax, rsi           ; count * size
    add rax, 16             ; + header
    cmp rax, LIMIT
    ja .too_big
    jmp .done
.too_big:
    mov rax, -1
.done:
