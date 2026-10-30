%include "level176.inc"

global _start

section .text
_start:
    mov rdi, [secret]       ; status; the kernel keeps only the low 8 bits
    mov eax, 60             ; exit
    syscall
