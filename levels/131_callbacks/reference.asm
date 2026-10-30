global map
global filter
global reduce

section .text
map:                            ; rdi = arr, rsi = n, rdx = fn
    push rbx
    push r12
    push r13
    push r14
    sub rsp, 8                  ; 4 pushes + padding: aligned
    mov rbx, rdi
    mov r12, rsi
    mov r13, rdx
    xor r14d, r14d
.next:
    cmp r14, r12
    jae .done
    mov rdi, [rbx + r14*8]
    call r13                    ; indirect call through the pointer
    mov [rbx + r14*8], rax
    inc r14
    jmp .next
.done:
    add rsp, 8
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

filter:                         ; rdi = arr, rsi = n, rdx = pred -> rax = kept
    push rbx
    push r12
    push r13
    push r14
    push r15                    ; 5 pushes: aligned
    mov rbx, rdi
    mov r12, rsi
    mov r13, rdx
    xor r14d, r14d              ; read index
    xor r15d, r15d              ; write index
.next:
    cmp r14, r12
    jae .done
    mov rdi, [rbx + r14*8]
    call r13
    test rax, rax
    jz .skip
    mov rax, [rbx + r14*8]
    mov [rbx + r15*8], rax
    inc r15
.skip:
    inc r14
    jmp .next
.done:
    mov rax, r15
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

reduce:                         ; rdi = arr, rsi = n, rdx = fn, rcx = init -> rax
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov rbx, rdi
    mov r12, rsi
    mov r13, rdx
    mov r15, rcx                ; acc
    xor r14d, r14d
.next:
    cmp r14, r12
    jae .done
    mov rdi, r15
    mov rsi, [rbx + r14*8]
    call r13
    mov r15, rax
    inc r14
    jmp .next
.done:
    mov rax, r15
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret
