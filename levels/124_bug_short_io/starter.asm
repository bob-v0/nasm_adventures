; Level 124 — Bug: Short Reads, Short Writes
;
; Copies stdin to stdout. With a file as input it works. When the input arrives
; through a pipe, or stdout is a slow pipe, data goes missing.
; Fix it: copy everything, whatever sizes read and write return.

BUF_SIZE equ 65536

global _start

section .text
_start:
    xor eax, eax                ; read(0, buf, BUF_SIZE)
    xor edi, edi
    mov rsi, buf
    mov edx, BUF_SIZE
    syscall
    mov rdx, rax                ; write(1, buf, n)
    mov eax, 1
    mov edi, 1
    mov rsi, buf
    syscall
    mov eax, 60                 ; exit(0)
    xor edi, edi
    syscall

section .bss
buf: resb BUF_SIZE
