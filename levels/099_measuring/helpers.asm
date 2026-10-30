; Level 99: functions the game asks you to measure. Each is an ordinary function (it
; may change the caller-saved registers).
global f_chain, f_sum, f_div, f_branchy

section .text
f_chain:                        ; 60 dependent multiplies
    mov rax, 3
%rep 60
    imul rax, rax
%endrep
    ret

f_sum:                          ; adds up 512 bytes (cold the first time)
    lea rsi, [table]
    xor eax, eax
%assign i 0
%rep 64
    add rax, [rsi + i]
%assign i i + 8
%endrep
    ret

f_div:                          ; 8 divisions in a row
    mov rax, 1000000007
    mov ecx, 3
%rep 8
    xor edx, edx
    div rcx
    add rax, 1000000
%endrep
    ret

f_branchy:                      ; a loop with a well-predicted branch
    mov ecx, 40
    xor eax, eax
.l:
    add rax, rcx
    dec ecx
    jnz .l
    ret

section .bss
alignb 64
table: resb 512
