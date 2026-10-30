; Level 158 — reference fix
;
; 2^61 records of 8 bytes: 2^64 bytes, which wraps to 0, and 0 + 16 passes the check.
;! witness rdi = 0x2000000000000000, rsi = 8

LIMIT equ 1 << 20

    mov rax, rdi
    mul rsi                 ; unsigned, full 128-bit product...
    jc .too_big             ; ...CF = 1 if it didn't fit in 64 bits
    add rax, 16
    jc .too_big             ; the header can wrap too
    cmp rax, LIMIT
    ja .too_big
    jmp .done
.too_big:
    mov rax, -1
.done:
