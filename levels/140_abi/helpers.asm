; Provided by level 140. ring_square(x) returns x * x, and then, like any function
; is allowed to, leaves garbage in every caller-saved register.
bits 64
global ring_square
global ring_calls

section .text
ring_square:
    inc qword [ring_calls]
    mov rax, rdi
    imul rax, rdi
    mov rcx, 0x5C5C5C5C5C5C5C5C     ; caller-saved registers: anything goes
    mov rdx, rcx
    mov rsi, rcx
    mov rdi, rcx
    mov r8, rcx
    mov r9, rcx
    mov r10, rcx
    mov r11, rcx
    ret

section .data
ring_calls: dq 0
