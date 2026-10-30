; Reference for check-levels (seed 1234). Players' keys differ.
global _start

section .text
_start:
    mov eax, 1
    mov edi, 1
    mov rsi, key
    mov edx, 8
    syscall
    mov eax, 60
    xor edi, edi
    syscall

section .data
key: dq 0x214ae199ab3dde9e
