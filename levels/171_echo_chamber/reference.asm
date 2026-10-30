global _start

section .text
_start:
    xor eax, eax            ; read(0, buf, 8)
    xor edi, edi
    mov rsi, buf
    mov edx, 8
    syscall
    mov r12, rax            ; r12 survives syscalls; rax/rcx/r11 do not

    mov rax, [buf]          ; reverse the 8 bytes in one go
    bswap rax
    mov [buf], rax

    mov eax, 1              ; write(1, prefix, PREFIX_LEN)
    mov edi, 1
    mov rsi, prefix
    mov edx, PREFIX_LEN
    syscall

    mov eax, 1              ; write(1, buf, 8)
    mov edi, 1
    mov rsi, buf
    mov edx, 8
    syscall

    mov eax, 1              ; write(1, newline, 1)
    mov edi, 1
    mov rsi, newline
    mov edx, 1
    syscall

    mov rdi, r12            ; exit(bytes read)
    mov eax, 60
    syscall

section .data
prefix:     db "echo: "
PREFIX_LEN  equ $ - prefix
newline:    db 10

section .bss
buf: resb 8
