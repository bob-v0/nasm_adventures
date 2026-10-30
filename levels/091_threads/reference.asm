; Level 91 — Threads (reference)
global ring_parallel_sum

MAX_THREADS equ 8
STACK       equ 16384
; one job per thread
J_START  equ 0                  ; first value
J_COUNT  equ 8
J_RESULT equ 16
J_TID    equ 24                 ; set by clone, zeroed by the kernel when the thread ends
J_SIZE   equ 32
CLONE_FLAGS equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000
;               VM      FS      FILES   SIGHAND THREAD    SYSVSEM   PARENT_SETTID CHILD_CLEARTID

section .text
ring_parallel_sum:              ; rdi = values, rsi = n, rdx = k (1..8)
    push rbx
    push r12
    push r13
    push r14
    push r15
    mov r13, rdi
    mov r14, rsi
    mov r15, rdx
    mov rax, r14                ; each thread gets n / k values; the last also the rest
    xor edx, edx
    div r15
    mov rcx, rax                ; per = n / k
    xor ebx, ebx
.split:
    cmp rbx, r15
    jae .spawn_all
    imul r12, rbx, J_SIZE
    lea r12, [jobs + r12]
    mov rax, rbx
    imul rax, rcx
    lea rax, [r13 + rax*8]
    mov [r12 + J_START], rax
    mov [r12 + J_COUNT], rcx
    mov qword [r12 + J_RESULT], 0
    lea rax, [r15 - 1]
    cmp rbx, rax
    jne .next_split
    mov rax, rcx                ; the last job: up to the end
    imul rax, rbx
    mov rdx, r14
    sub rdx, rax
    mov [r12 + J_COUNT], rdx
.next_split:
    inc rbx
    jmp .split
.spawn_all:
    xor ebx, ebx
.spawn:
    cmp rbx, r15
    jae .join_all
    imul r12, rbx, J_SIZE
    lea r12, [jobs + r12]       ; the new thread finds its job in r12 (registers are copied)
    mov eax, 56                 ; clone(flags, stack top, &job.tid, &job.tid, 0)
    mov edi, CLONE_FLAGS
    lea rsi, [rbx + 1]
    imul rsi, rsi, STACK
    lea rsi, [stacks + rsi]
    lea rdx, [r12 + J_TID]
    lea r10, [r12 + J_TID]
    xor r8d, r8d
    syscall
    test rax, rax
    jz worker                   ; we're the new thread
    inc rbx
    jmp .spawn
.join_all:
    xor ebx, ebx
    xor r13d, r13d              ; the total
.join:
    cmp rbx, r15
    jae .done
    imul r12, rbx, J_SIZE
    lea r12, [jobs + r12]
.wait:
    mov edx, [r12 + J_TID]      ; 0: the thread has ended
    test edx, edx
    jz .joined
    mov eax, 202                ; futex(&job.tid, FUTEX_WAIT, tid, 0): sleep while it's tid
    lea rdi, [r12 + J_TID]
    xor esi, esi
    xor r10d, r10d
    syscall
    jmp .wait
.joined:
    add r13, [r12 + J_RESULT]
    inc rbx
    jmp .join
.done:
    mov rax, r13
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

worker:                         ; r12 = this thread's job
    mov rsi, [r12 + J_START]
    mov rcx, [r12 + J_COUNT]
    xor eax, eax
    test rcx, rcx
    jz .store
.add:
    add rax, [rsi]
    add rsi, 8
    dec rcx
    jnz .add
.store:
    mov [r12 + J_RESULT], rax
    mov eax, 60                 ; exit: ends this thread only
    xor edi, edi
    syscall

section .bss
alignb 16
jobs:   resb J_SIZE * MAX_THREADS
alignb 16
stacks: resb STACK * MAX_THREADS
