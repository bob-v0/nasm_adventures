; Level 114 — Dynamic Linking (reference)
default rel

extern strlen, printf, puts, dlsym
global main

section .text
main:                           ; main(argc, argv)
    push rbx
    push r12
    push r13
    mov r12d, edi
    mov r13, rsi
    mov ebx, 1
.next:
    cmp ebx, r12d
    jge .check
    mov rdi, [r13 + rbx*8]
    call [rel strlen wrt ..got] ; the GOT slot holds strlen's address: call through it
    lea rdi, [fmt]
    mov rsi, [r13 + rbx*8]
    mov rdx, rax
    xor eax, eax                ; variadic: no vector registers
    call [rel printf wrt ..got]
    inc ebx
    jmp .next
.check:
    xor edi, edi                ; dlsym(RTLD_DEFAULT, "puts"): ask ld.so directly
    lea rsi, [puts_name]
    call [rel dlsym wrt ..got]
    lea rdi, [agree]
    cmp rax, [rel puts wrt ..got]
    je .say
    lea rdi, [disagree]
.say:
    call [rel puts wrt ..got]
    xor eax, eax
    pop r13
    pop r12
    pop rbx
    ret

section .rodata
fmt:       db "%s: %zu", 10, 0
puts_name: db "puts", 0
agree:     db "the GOT and dlsym agree on puts", 0
disagree:  db "the GOT and dlsym disagree on puts", 0
