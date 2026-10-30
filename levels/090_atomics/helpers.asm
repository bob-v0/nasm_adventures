; Level 90's harness (the game's): THREADS threads, each ROUNDS times:
;   t = atomic_fetch_add(&next_ticket, 1)    -> tickets[t] += 1 (each must end at exactly 1)
;   atomic_max(&biggest, its value)
;   old = atomic_swap(&token, its value)     -> every value comes back out exactly once
global _start, tickets, biggest, token, swapped, nswapped, values
extern atomic_fetch_add, atomic_swap, atomic_max

THREADS equ 4
ROUNDS  equ 24
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000

section .text
_start:
    xor ebx, ebx
.spawn:
    cmp ebx, THREADS
    je .join
    mov r12, rbx                ; the thread's number, in a register it inherits
    mov eax, 56
    mov edi, CLONE
    lea rsi, [rbx + 1]
    shl rsi, 13
    lea rsi, [stacks + rsi]
    lea rdx, [tids + rbx*4]
    mov r10, rdx
    xor r8d, r8d
    syscall
    test rax, rax
    jz worker
    inc ebx
    jmp .spawn
.join:
    xor ebx, ebx
.next:
    cmp ebx, THREADS
    je .done
.wait:
    mov edx, [tids + rbx*4]
    test edx, edx
    jz .joined
    mov eax, 202
    lea rdi, [tids + rbx*4]
    xor esi, esi
    xor r10d, r10d
    syscall
    jmp .wait
.joined:
    inc ebx
    jmp .next
.done:
    mov eax, 231
    xor edi, edi
    syscall

worker:                         ; r12 = thread number
    xor r13d, r13d              ; round
.round:
    cmp r13, ROUNDS
    je .exit
    lea rdi, [next_ticket]
    mov esi, 1
    call atomic_fetch_add
    cmp rax, THREADS * ROUNDS
    jae .bad_ticket
    lock inc qword [tickets + rax*8]
.bad_ticket:
    imul r14, r12, ROUNDS       ; this round's value: unique, 1-based
    lea r14, [r14 + r13 + 1]
    mov rax, [values + r14*8]
    mov r15, rax
    lea rdi, [biggest]
    mov rsi, r15
    call atomic_max
    lea rdi, [token]
    mov rsi, r15
    call atomic_swap
    mov ecx, 1                  ; remember what came back
    lock xadd [nswapped], rcx
    mov [swapped + rcx*8], rax
    inc r13
    jmp .round
.exit:
    mov eax, 60
    xor edi, edi
    syscall

section .bss
alignb 64
next_ticket: resq 8
biggest:     resq 8
token:       resq 8
nswapped:    resq 8
tickets:     resq THREADS * ROUNDS
swapped:     resq THREADS * ROUNDS
values:      resq THREADS * ROUNDS + 1
tids:        resd THREADS
alignb 16
stacks:      resb (THREADS + 1) * 8192
