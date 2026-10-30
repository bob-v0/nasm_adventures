; Level 87's harness (the game's): THREADS threads, each ROUNDS times: take the lock, do
; a slow non-atomic update of a shared total (a read, some work, a write), unlock.
global _start, total
extern mutex_lock, mutex_unlock

THREADS equ 4
ROUNDS  equ 25
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000

section .text
_start:
    xor ebx, ebx
.spawn:
    cmp ebx, THREADS
    je .join
    mov eax, 56
    mov edi, CLONE
    lea rsi, [rbx + 1]
    shl rsi, 12
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

worker:
    mov r12d, ROUNDS
.round:
    lea rdi, [the_lock]
    call mutex_lock
    mov rax, [total]            ; the critical section: slow, and not atomic at all
    mov ecx, 40
.work:
    dec ecx
    jnz .work
    inc rax
    mov [total], rax
    lea rdi, [the_lock]
    call mutex_unlock
    dec r12d
    jnz .round
    mov eax, 60
    xor edi, edi
    syscall

section .bss
alignb 64
the_lock: resd 16
total:    resq 1
tids:     resd THREADS
alignb 16
stacks:   resb (THREADS + 1) * 4096
