; Level 84 — Livelock & Starvation
;
; Four threads share a lock, 15 short critical sections each. Every "I want the lock"
; and "I got it" is logged. A fair lock lets nobody wait while the same others get in
; again and again: with 4 threads, a waiting thread may be overtaken at most 3 times
; (the game allows 5: the log entry comes a moment before the lock call).
; This test-and-set spinlock is correct (one holder at a time) but not fair: a thread
; that just released it often grabs it right back.
;
; 1. Find a schedule where a thread is overtaken more than 5 times while waiting:
;        ;! witness schedule = N
; 2. Make the lock fair.

global _start, events, nevents

THREADS equ 4
ROUNDS  equ 15
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000

section .text
_start:
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
    mov r13d, ROUNDS
.round:
    mov edi, 1                  ; log: I want it
    call log
    call acquire
    mov edi, 2                  ; log: I got it
    call log
    mov ecx, 8                  ; a short critical section
.work:
    dec ecx
    jnz .work
    call release
    dec r13d
    jnz .round
    mov eax, 60
    xor edi, edi
    syscall

log:                            ; edi = 1 (want) / 2 (got), r12 = thread
    shl edi, 8
    or edi, r12d
    mov eax, 1
    lock xadd [nevents], rax
    mov [events + rax*4], edi
    ret

; ---- the lock ------------------------------------------------------------------------

acquire:
    mov eax, 1
    xchg eax, [the_lock]
    test eax, eax
    jz .got
    pause
    jmp acquire
.got:
    ret

release:
    mov dword [the_lock], 0
    ret

section .bss
alignb 64
the_lock:  resd 16
nevents:   resq 1
events:    resd 2 * THREADS * ROUNDS
tids:      resd THREADS
alignb 16
stacks:    resb (THREADS + 1) * 4096
