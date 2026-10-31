; Level 54 — Disassembler
;
; Read machine code from stdin (at most 64 KiB) and print it as NASM source, one
; instruction per line, exactly in the format of the brief:
;
;     mov rax, [rbx+rcx*8+0x10]
;     add dword [rbp-0x4], 0x1
;     jne 0x2a
;
; The code is at address 0: the first byte is offset 0x0. Every input is a sequence of
; instructions from the subset in the brief.

global _start

section .text
_start:
    ; TODO
    mov eax, 60
    xor edi, edi
    syscall
