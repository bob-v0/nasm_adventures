global hanoi

section .text
hanoi:                          ; rdi = n, rsi = from, rdx = to, rcx = via, r8 = out
    mov rax, r8
    test rdi, rdi
    jz .base
    push rbx                    ; n
    push r12                    ; from
    push r13                    ; to
    push r14                    ; via  (4 pushes + return address: rsp % 16 == 8)
    sub rsp, 8                  ; ...so pad to keep calls aligned
    mov rbx, rdi
    mov r12, rsi
    mov r13, rdx
    mov r14, rcx

    lea rdi, [rbx - 1]          ; hanoi(n - 1, from, via, to, out)
    mov rsi, r12
    mov rdx, r14
    mov rcx, r13
    call hanoi                  ; r8 = out, still untouched
    mov [rax], r12b             ; move disk n: from -> to
    mov [rax + 1], r13b
    lea r8, [rax + 2]
    lea rdi, [rbx - 1]          ; hanoi(n - 1, via, to, from, out)
    mov rsi, r14
    mov rdx, r13
    mov rcx, r12
    call hanoi

    add rsp, 8
    pop r14
    pop r13
    pop r12
    pop rbx
.base:
    ret
