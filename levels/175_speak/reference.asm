%include "level175.inc"

global _start

section .text
_start:
    mov eax, 1              ; write(1, hello, HELLO_LEN)
    mov edi, 1
    mov rsi, hello
    mov edx, HELLO_LEN
    syscall

    mov eax, 1              ; write(1, name, NAME_LEN)
    mov edi, 1
    mov rsi, name
    mov edx, NAME_LEN
    syscall

    mov eax, 1              ; write(1, bang, BANG_LEN)
    mov edi, 1
    mov rsi, bang
    mov edx, BANG_LEN
    syscall

    mov eax, 1              ; write(2, warn, WARN_LEN)
    mov edi, 2
    mov rsi, warn
    mov edx, WARN_LEN
    syscall

    mov edi, eax            ; exit(bytes written to stderr)
    mov eax, 60
    syscall

section .data
hello:     db "Hello, "
HELLO_LEN  equ $ - hello
bang:      db `!\n`
BANG_LEN   equ $ - bang
warn:      db `warning: the walls have ears\n`
WARN_LEN   equ $ - warn
