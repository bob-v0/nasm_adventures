; wc: counts the lines on stdin and prints the number.
%include "_common.inc"
global _start
section .text
_start:
    xor r12d, r12d
.read:
    xor eax, eax
    xor edi, edi
    lea rsi, [buf]
    mov edx, 4096
    syscall
    test rax, rax
    jle .print
    xor ecx, ecx
.scan:
    cmp byte [buf + rcx], 10
    jne .no
    inc r12
.no:
    inc rcx
    cmp rcx, rax
    jb .scan
    jmp .read
.print:
    lea rsi, [num + 20]
    mov byte [rsi], 10
    mov rax, r12
    mov ecx, 10
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test rax, rax
    jnz .digit
    lea rdx, [num + 21]
    sub rdx, rsi
    WRITE 1, rsi, rdx
    EXIT 0
section .bss
buf: resb 4096
num: resb 21
