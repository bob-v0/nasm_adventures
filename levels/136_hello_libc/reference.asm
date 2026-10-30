default rel                     ; RIP-relative addresses (explained in Arc V)

extern printf
extern scanf
global main

section .text
main:                           ; rsp % 16 == 8
    push rbx                    ; i
    push r12                    ; n
    push r13                    ; sum of cubes
    sub rsp, 16                 ; aligned; [rsp] holds n from scanf
    lea rdi, [in_fmt]
    lea rsi, [rsp]              ; &n
    xor eax, eax                ; variadic: no vector registers
    call scanf
    mov r12, [rsp]
    xor r13d, r13d
    mov ebx, 1
.row:
    cmp rbx, r12
    ja .total
    mov rdx, rbx
    imul rdx, rbx               ; i^2
    mov rcx, rdx
    imul rcx, rbx               ; i^3
    add r13, rcx
    lea rdi, [row_fmt]
    mov rsi, rbx
    xor eax, eax
    call printf
    inc rbx
    jmp .row
.total:
    lea rdi, [sum_fmt]
    mov rsi, r13
    xor eax, eax
    call printf
    xor eax, eax                ; return 0
    add rsp, 16
    pop r13
    pop r12
    pop rbx
    ret

section .rodata
in_fmt:  db "%ld", 0
row_fmt: db "%2ld %4ld %6ld", 10, 0
sum_fmt: db "sum of cubes: %ld", 10, 0
