; pwd: prints the current directory.
%include "_common.inc"
global _start
section .text
_start:
    mov eax, 79                 ; getcwd(buf, 4096): returns the length including the NUL
    lea rdi, [buf]
    mov esi, 4096
    syscall
    test rax, rax
    jle .fail
    mov byte [buf + rax - 1], 10
    WRITE 1, buf, rax
    EXIT 0
.fail:
    EXIT 1
section .bss
buf: resb 4096
