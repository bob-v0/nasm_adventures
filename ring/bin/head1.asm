; head1: copies the first line of stdin to stdout, then exits.
%include "_common.inc"
global _start
section .text
_start:
.read:
    xor eax, eax
    xor edi, edi
    lea rsi, [one]
    mov edx, 1
    syscall
    test rax, rax
    jle .done
    WRITE 1, one, 1
    cmp byte [one], 10
    jne .read
.done:
    EXIT 0
section .bss
one: resb 1
