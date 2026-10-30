extern ring_square
global poly

section .text
poly:
    push rbx                    ; prologue: we need four values to survive the call
    push r12
    push r13
    push r14
    mov rbx, rdi                ; x
    mov r12, rsi                ; a
    mov r13, rdx                ; b
    mov r14, rcx                ; c
    call ring_square            ; rax = x*x; scratch registers are now garbage
    imul rax, r12               ; a*x^2
    mov rdx, r13
    imul rdx, rbx               ; b*x
    add rax, rdx
    add rax, r14
    pop r14                     ; epilogue: reverse order
    pop r13
    pop r12
    pop rbx
    ret
