; Level 75 — Memory Reclamation
;
; Level 77's lock-free stack, with nodes from the heap: four threads each allocate and
; push 30 values, and pop and free nodes as they go; the main thread frees what's left.
; Under some schedules the game's checked allocator stops it: "use after free".
;
; 1. Find such a schedule:   ;! witness schedule = N
; 2. Fix it: a node may only be freed once no thread can still be reading it. (Hint:
;    hazard pointers. Every node must still be freed by the end.)

global _start

THREADS equ 4
ROUNDS  equ 30
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000
SYS_MALLOC equ 0x1000           ; the game's checked allocator
SYS_FREE   equ 0x1001
; a node: dq next, dq value

section .text
_start:
    xor ebx, ebx
.spawn:
    cmp ebx, THREADS
    je .join
    mov r12, rbx                ; my thread number
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
.drain:                         ; everyone's gone: free what's left
    mov rdi, r12
    call pop
    test rax, rax
    jz .done
    mov rdi, rax
    call free
    jmp .drain
.done:
    mov eax, 1
    mov edi, 1
    lea rsi, [msg]
    mov edx, MSG_LEN
    syscall
    mov eax, 231
    xor edi, edi
    syscall

worker:                         ; r12 = me
    mov r13d, ROUNDS
.round:
    mov edi, 16
    call malloc
    mov [rax + 8], r13          ; a value
    mov rsi, rax
    call push
    mov rdi, r12
    call pop
    test rax, rax
    jz .again
    mov rdi, rax                ; done with it
    call free
.again:
    dec r13d
    jnz .round
    mov eax, 60
    xor edi, edi
    syscall

; ---- the stack ----------------------------------------------------------------------

push:                           ; rsi = node
    mov rax, [top]
.retry:
    mov [rsi], rax
    lock cmpxchg [top], rsi
    jnz .retry
    ret

pop:                            ; rdi = my thread number -> rax = node or 0
    mov rax, [top]
.retry:
    test rax, rax
    jz .empty
    mov rdx, [rax]              ; top.next
    lock cmpxchg [top], rdx
    jnz .retry
.empty:
    ret

; ---- the heap -------------------------------------------------------------------------

malloc:                         ; rdi = size -> rax
    mov eax, SYS_MALLOC
    syscall
    ret

free:                           ; rdi = block
    mov eax, SYS_FREE
    syscall
    ret

section .data
msg: db "done", 10
MSG_LEN equ $ - msg

section .bss
alignb 64
top:     resq 8
hazards: resq 8 * THREADS       ; one cache line per thread, zeroed (yours to use)
tids:    resd THREADS
alignb 16
stacks:  resb (THREADS + 1) * 8192
