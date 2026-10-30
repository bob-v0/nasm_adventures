; Provided by level 129: a generator built on your co_switch.
;   ring_fib(n): runs a Fibonacci generator as a coroutine on its own stack, resuming
;   it n times and storing each value it yields in `results`. Returns n.
; Context layout (7 qwords): rsp, rbx, rbp, r12, r13, r14, r15
bits 64
global ring_fib
global results
global ring_corrupted
extern co_switch

section .text
ring_fib:                       ; rdi = n
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    sub rsp, 8                  ; 6 pushes + padding: aligned
    mov rbx, rdi                ; n
    xor r12d, r12d              ; count
    mov r13, 0x1313131313131313 ; values that must survive every switch
    mov r14, 0x1414141414141414
    mov r15, 0x1515151515151515
    mov rbp, 0x0B0B0B0B0B0B0B0B
    ; A fresh context for the generator: its stack holds just the address to "return" to.
    lea rax, [gen_stack + 4096 - 8]
    lea rcx, [fib_gen]
    mov [rax], rcx
    mov [gen_ctx], rax
.loop:
    cmp r12, rbx
    jae .done
    lea rdi, [main_ctx]         ; save us, resume the generator
    lea rsi, [gen_ctx]
    call co_switch
    mov rax, [yielded]
    mov [results + r12*8], rax
    inc r12
    jmp .loop
.done:
    mov rax, 0x1313131313131313
    cmp r13, rax
    jne .corrupt
    mov rax, 0x1414141414141414
    cmp r14, rax
    jne .corrupt
    mov rax, 0x1515151515151515
    cmp r15, rax
    jne .corrupt
    mov rax, 0x0B0B0B0B0B0B0B0B
    cmp rbp, rax
    je .ok
.corrupt:
    inc qword [ring_corrupted]
.ok:
    mov rax, r12
    add rsp, 8
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    pop rbx
    ret

fib_gen:                        ; runs on gen_stack; never returns
    xor r12d, r12d              ; a   (its own r12/r13, separate from ring_fib's)
    mov r13d, 1                 ; b
.yield:
    mov [yielded], r12
    lea rdi, [gen_ctx]          ; save the generator, resume the caller
    lea rsi, [main_ctx]
    call co_switch
    lea rax, [r12 + r13]
    mov r12, r13
    mov r13, rax
    jmp .yield

section .data
ring_corrupted: dq 0
yielded:        dq 0
results:        times 100 dq 0

section .bss
alignb 16
gen_stack: resb 4096
main_ctx:  resq 7
gen_ctx:   resq 7
