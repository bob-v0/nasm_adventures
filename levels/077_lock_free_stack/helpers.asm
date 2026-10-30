; Level 77's harness (the game's): THREADS threads each push their NODES nodes onto one
; shared stack, popping one after every second push. When they're done, the main thread
; pops what's left. Every node must come out exactly once. (Nodes are never reused.)
; A node: dq next, dq value.
global _start, popped, npopped, nodes
extern stack_push, stack_pop

THREADS equ 4
NODES   equ 30
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000

section .text
_start:
    xor ebx, ebx                ; node i's value = i + 1
.init:
    mov rax, rbx
    shl rax, 4
    lea rcx, [rbx + 1]
    mov [nodes + rax + 8], rcx
    inc ebx
    cmp ebx, THREADS * NODES
    jb .init
    xor ebx, ebx
.spawn:
    cmp ebx, THREADS
    je .join
    mov r12, rbx
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
    je .drain
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
.drain:
    lea rdi, [stack]
    call stack_pop
    test rax, rax
    jz .done
    call record
    jmp .drain
.done:
    mov eax, 231
    xor edi, edi
    syscall

worker:                         ; r12 = thread number
    xor r13d, r13d
.push:
    imul rax, r12, NODES
    add rax, r13
    shl rax, 4
    lea rsi, [nodes + rax]
    lea rdi, [stack]
    call stack_push
    test r13d, 1
    jz .next
    lea rdi, [stack]
    call stack_pop
    test rax, rax
    jz .next
    call record
.next:
    inc r13d
    cmp r13d, NODES
    jb .push
    mov eax, 60
    xor edi, edi
    syscall

record:                         ; rax = a popped node: remember its value
    mov rdx, [rax + 8]
    mov eax, 1
    lock xadd [npopped], rax
    cmp rax, 2 * THREADS * NODES
    jae .full
    mov [popped + rax*8], rdx
.full:
    ret

section .bss
alignb 64
stack:   resq 8                 ; your stack: zeroed (its first qword can be the top)
npopped: resq 8
popped:  resq 2 * THREADS * NODES
alignb 16
nodes:   resq 2 * THREADS * NODES
tids:    resd THREADS
alignb 16
stacks:  resb (THREADS + 1) * 4096
