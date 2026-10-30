; Level 95 — Prefetch & TLB (reference)
;
; One list at a time, each node's address comes from the node before: one 200-cycle
; trip to memory after another. The k lists are independent, though: walk them all at
; once, one step each per round, and k misses are in flight together. Huge pages cover
; the pool with 2 TLB entries instead of 1024.

global ring_sum_lists
extern pool

section .text
ring_sum_lists:                 ; rdi = heads, rsi = k
    push rbx
    push r12
    push r13
    mov r12, rdi
    mov r13, rsi
    mov eax, 28                 ; madvise(pool, 4 MiB, MADV_HUGEPAGE)
    lea rdi, [pool]
    mov esi, 4 << 20
    mov edx, 14
    syscall
    xor ecx, ecx                ; cur[i] = heads[i]
.copy:
    cmp rcx, r13
    jae .round
    mov rdx, [r12 + rcx*8]
    mov [cur + rcx*8], rdx
    inc rcx
    jmp .copy
.round:
    xor eax, eax
    xor ebx, ebx                ; did any list move this round?
.again:
    xor ecx, ecx
    xor ebx, ebx
.step:
    mov rdx, [cur + rcx*8]
    test rdx, rdx
    jz .skip
    add rax, [rdx + 8]
    mov rdx, [rdx]
    mov [cur + rcx*8], rdx
    mov ebx, 1
.skip:
    inc rcx
    cmp rcx, r13
    jb .step
    test ebx, ebx
    jnz .again
    pop r13
    pop r12
    pop rbx
    ret

section .bss
cur: resq 8
