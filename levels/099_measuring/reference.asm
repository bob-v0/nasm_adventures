; Level 99 — Measuring (reference)
global ring_measure

RUNS equ 40

section .text
ring_measure:                   ; rdi = a function: its cost in cycles, measured properly
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov rbx, rdi
    call rbx                    ; warm up: caches, branch predictors
    call rbx
    lea rdi, [nothing]          ; the cost of measuring itself: an empty function
    call best_of
    mov r15, rax
    mov rdi, rbx
    call best_of
    sub rax, r15
    jns .ok
    xor eax, eax
.ok:
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

best_of:                        ; rdi = function: the smallest of RUNS fenced timings
    push rbx
    push r12
    push r13
    mov rbx, rdi
    mov r12, -1                 ; the best so far
    mov r13d, RUNS
.run:
    lfence                      ; nothing earlier may still be running
    rdtsc
    shl rdx, 32
    or rax, rdx
    mov [start], rax
    lfence                      ; nothing later may start before the clock is read
    call rbx
    rdtscp                      ; waits until everything before it has finished
    lfence
    shl rdx, 32
    or rax, rdx
    sub rax, [start]
    cmp rax, r12
    jae .next
    mov r12, rax                ; interrupts only ever add time: keep the minimum
.next:
    dec r13d
    jnz .run
    mov rax, r12
    pop r13
    pop r12
    pop rbx
    ret

nothing:
    ret

section .bss
start: resq 1
