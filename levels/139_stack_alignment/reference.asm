extern ring_square
global sum_squares

section .text
sum_squares:                    ; rsp % 16 == 8
    push rbx                    ; == 0
    push r12                    ; == 8
    push r13                    ; == 0
    push r14                    ; == 8
    sub rsp, 8                  ; == 0: aligned for our calls
    mov rbx, rdi                ; n
    mov r12, rsi                ; k
    xor r13d, r13d              ; sum
    mov r14d, 1                 ; i
.loop:
    cmp r14, rbx
    ja .done
    mov rdi, r14
    imul rdi, r12               ; i * k
    call ring_square
    add r13, rax
    inc r14
    jmp .loop
.done:
    mov rax, r13
    add rsp, 8
    pop r14
    pop r13
    pop r12
    pop rbx
    ret
