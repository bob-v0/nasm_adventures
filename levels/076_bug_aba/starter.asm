; Level 76 — ABA
;
; A free list of 8 nodes as level 77's lock-free stack. Four threads repeatedly take a
; node (pop), claim it (its owner field goes from 0 to the thread's number + 1, with a
; cmpxchg that would notice if someone else had it), use it, release it and push it back.
; No node should ever have two owners. Under some schedules, one does: the program prints
; "double owners: N" with N > 0 instead of 0.
;
; 1. Find such a schedule:   ;! witness schedule = N
; 2. Fix the stack.

global _start

THREADS equ 4
ROUNDS  equ 25
NNODES  equ 8
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000
; a node: dq next, dq owner (0 = free), then some data

section .text
_start:
    xor ebx, ebx                ; put the nodes on the free list
.init:
    mov rsi, rbx
    shl rsi, 5
    lea rsi, [nodes + rsi]
    lea rdi, [freelist]
    call stack_push
    inc ebx
    cmp ebx, NNODES
    jb .init
    xor ebx, ebx
.spawn:
    cmp ebx, THREADS
    je .join
    lea r12, [rbx + 1]          ; owner id
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
    je .report
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
.report:
    mov eax, [double]
    cmp eax, 9
    jbe .digit
    mov eax, 9
.digit:
    add al, '0'
    mov [msg_n], al
    mov eax, 1
    mov edi, 1
    lea rsi, [msg]
    mov edx, MSG_LEN
    syscall
    mov eax, 231
    xor edi, edi
    syscall

worker:                         ; r12 = my owner id
    mov r13d, ROUNDS
.round:
    lea rdi, [freelist]
    call stack_pop
    test rax, rax
    jz .again                   ; all taken: try again
    mov rbx, rax
    xor eax, eax                ; claim it: owner 0 -> me
    lock cmpxchg [rbx + 8], r12
    jz .mine
    lock inc dword [double]     ; someone else owns it too!
    jmp .again
.mine:
    mov ecx, 3                  ; use it
.use:
    mov [rbx + 16], r12
    dec ecx
    jnz .use
    mov qword [rbx + 8], 0      ; release it and give it back
    lea rdi, [freelist]
    mov rsi, rbx
    call stack_push
.again:
    dec r13d
    jnz .round
    mov eax, 60
    xor edi, edi
    syscall

; ---- the free list: level 77's lock-free stack ------------------------------------------

stack_push:                     ; rdi = stack, rsi = node
    mov rax, [rdi]
.retry:
    mov [rsi], rax
    lock cmpxchg [rdi], rsi
    jnz .retry
    ret

stack_pop:                      ; rdi = stack -> rax = node or 0
    mov rax, [rdi]
.retry:
    test rax, rax
    jz .empty
    mov rdx, [rax]              ; top.next
    lock cmpxchg [rdi], rdx
    jnz .retry
.empty:
    ret

section .data
msg:   db "double owners: "
msg_n: db "?", 10
MSG_LEN equ $ - msg

section .bss
alignb 16
freelist: resq 2                ; the top pointer (and 8 more zeroed bytes after it)
double:   resd 1
alignb 32
nodes:    resb 32 * NNODES
tids:     resd THREADS
alignb 16
stacks:   resb (THREADS + 1) * 4096
