; Level 114 — Dynamic Linking
;
; This program calls libc through the PLT. Call every libc function through its GOT
; slot instead (no PLT at all), and keep the output the same:
;   for each argument: "ARG: LENGTH"
;   then: "the GOT and dlsym agree on puts", if the address in puts's GOT slot is the
;   one dlsym(RTLD_DEFAULT, "puts") returns.
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
    call strlen wrt ..plt
    lea rdi, [fmt]
    mov rsi, [r13 + rbx*8]
    mov rdx, rax
    xor eax, eax                ; variadic: no vector registers
    call printf wrt ..plt
    inc ebx
    jmp .next
.check:
    xor edi, edi                ; dlsym(RTLD_DEFAULT, "puts")
    lea rsi, [puts_name]
    call dlsym wrt ..plt
    lea rdi, [agree]
    lea rcx, [puts wrt ..plt]     ; TODO: this is the PLT stub, not puts
    cmp rax, rcx
    je .say
    lea rdi, [disagree]
.say:
    call puts wrt ..plt
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
