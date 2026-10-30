; Level 72's harness (the game's). It uses your runtime:
;   rt_init(workers)               start the worker threads
;   actor_new(behavior) -> actor   a new actor; the caller holds one reference
;   actor_send(actor, msg)         from any thread; msg: dq next, dq value
;   actor_release(actor)           drop a reference
;   rt_shutdown()                  wait until no message is in flight, stop the workers
; Four actors form a ring; a message with value h > 0 is passed on to the next actor
; with value h - 1. Two producer threads inject TOKENS tokens of HOPS hops each into
; actor 0. Every message is a heap block that `behavior` frees.
global _start, behavior, ring_actors, problems, processed
extern rt_init, actor_new, actor_send, actor_release, rt_shutdown

WORKERS   equ 3
RING      equ 4
PRODUCERS equ 2
TOKENS    equ 3                 ; per producer
HOPS      equ 6
TOTAL     equ PRODUCERS * TOKENS * (HOPS + 1)
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000
SYS_MALLOC equ 0x1000
SYS_FREE   equ 0x1001

section .text
_start:
    mov edi, WORKERS
    call rt_init
    xor ebx, ebx
.actors:
    lea rdi, [behavior]
    call actor_new
    mov [ring_actors + rbx*8], rax
    inc ebx
    cmp ebx, RING
    jb .actors
    xor ebx, ebx
.spawn:
    cmp ebx, PRODUCERS
    je .join
    mov eax, 56
    mov edi, CLONE
    lea rsi, [rbx + 1]
    shl rsi, 13
    lea rsi, [pstacks + rsi]
    lea rdx, [ptids + rbx*4]
    mov r10, rdx
    xor r8d, r8d
    syscall
    test rax, rax
    jz producer
    inc ebx
    jmp .spawn
.join:
    xor ebx, ebx
.next:
    cmp ebx, PRODUCERS
    je .shutdown
.wait:
    mov edx, [ptids + rbx*4]
    test edx, edx
    jz .joined
    mov eax, 202
    lea rdi, [ptids + rbx*4]
    xor esi, esi
    xor r10d, r10d
    syscall
    jmp .wait
.joined:
    inc ebx
    jmp .next
.shutdown:
    call rt_shutdown
    xor ebx, ebx
.release:
    mov rdi, [ring_actors + rbx*8]
    call actor_release
    inc ebx
    cmp ebx, RING
    jb .release
    mov eax, 231
    xor edi, edi
    syscall

producer:
    mov r12d, TOKENS
.token:
    mov edi, 16
    mov eax, SYS_MALLOC
    syscall
    mov qword [rax], 0
    mov qword [rax + 8], HOPS
    mov rsi, rax
    mov rdi, [ring_actors]
    call actor_send
    dec r12d
    jnz .token
    mov eax, 60
    xor edi, edi
    syscall

behavior:                       ; rdi = actor, rsi = msg (freed here)
    push rbx
    push r12
    push r13
    mov rbx, rdi
    mov r12, rsi
    xor ecx, ecx                ; which ring position is this actor?
.find:
    cmp [ring_actors + rcx*8], rbx
    je .found
    inc ecx
    cmp ecx, RING
    jb .find
    lock inc dword [problems + 8] ; not one of ours
    jmp .out
.found:
    mov r13, rcx
    mov eax, 1
    xchg eax, [running + r13*4]
    test eax, eax
    jz .alone
    lock inc dword [problems]   ; running on two workers at once
.alone:
    lock inc dword [processed]
    mov rax, [r12 + 8]
    test rax, rax
    jz .done
    dec rax                     ; pass it on: a new message to the next actor
    push rax
    mov edi, 16
    mov eax, SYS_MALLOC
    syscall
    pop rcx
    mov qword [rax], 0
    mov [rax + 8], rcx
    mov rsi, rax
    lea rcx, [r13 + 1]
    and ecx, RING - 1
    mov rdi, [ring_actors + rcx*8]
    call actor_send
.done:
    mov dword [running + r13*4], 0
    mov rdi, r12
    mov eax, SYS_FREE
    syscall
.out:
    pop r13
    pop r12
    pop rbx
    ret

section .bss
alignb 64
ring_actors: resq RING
running:     resd RING
problems:    resd 16           ; [0] ran twice at once, [2] unknown actor
processed:   resd 16
ptids:       resd PRODUCERS
alignb 16
pstacks:     resb (PRODUCERS + 1) * 8192
