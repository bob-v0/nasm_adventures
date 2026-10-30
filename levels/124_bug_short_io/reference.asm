; Level 124 — reference fix

BUF_SIZE equ 65536

global _start

section .text
_start:
.read_more:
    xor eax, eax                ; read(0, buf, BUF_SIZE)
    xor edi, edi
    mov rsi, buf
    mov edx, BUF_SIZE
    syscall
    test rax, rax
    jle .done                   ; 0 = end of input (or an error)
    mov r12, rax                ; bytes still to write
    mov r13, buf                ; from here
.write_more:
    mov rdx, r12                ; write(1, r13, r12)
    mov eax, 1
    mov edi, 1
    mov rsi, r13
    syscall
    test rax, rax
    jle .done
    add r13, rax                ; it may have written only part
    sub r12, rax
    jnz .write_more
    jmp .read_more
.done:
    mov eax, 60                 ; exit(0)
    xor edi, edi
    syscall

section .bss
buf: resb BUF_SIZE
