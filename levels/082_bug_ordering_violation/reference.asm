; Level 82 — Ordering Violation (reference)
;
; Peterson's algorithm (1981): mutual exclusion for two threads with nothing but loads
; and stores. It's proven correct... for a sequentially consistent machine. Two threads
; enter the critical section 20 times each; the program counts the times both were
; inside together. It should print "both inside: 0".
;
; 1. Find a schedule where both threads are inside:   ;! witness schedule = N
; 2. Fix it with as few fences as possible (the grader allows one per lock call).

global _start

ROUNDS equ 20
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000

section .text
_start:
    xor ebx, ebx
.spawn:
    cmp ebx, 2
    je .go
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
.go:
    mov eax, 1
    xchg eax, [go]
    xor ebx, ebx
.join:
    cmp ebx, 2
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
    jmp .join
.report:
    mov eax, [both]
    cmp eax, 9
    jbe .digit
    mov eax, 9                  ; (9 or more)
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

worker:                         ; r12 = me (0 or 1)
    pause
    cmp dword [go], 0
    je worker
    mov r13d, ROUNDS
.round:
    mov rdi, r12
    call peterson_lock
    lock inc dword [inside]     ; the critical section: is anyone else here?
    cmp dword [inside], 1
    je .alone
    lock inc dword [both]
.alone:
    mov ecx, 5
.work:
    dec ecx
    jnz .work
    lock dec dword [inside]
    mov rdi, r12
    call peterson_unlock
    dec r13d
    jnz .round
    mov eax, 60
    xor edi, edi
    syscall

; ---- the lock ------------------------------------------------------------------------

peterson_lock:                  ; rdi = me (0 or 1)
    mov esi, edi
    xor esi, 1                  ; the other thread
    mov dword [flag + rdi*4], 1 ; I want to enter
    mov [turn], esi             ; but you go first if you want to
    mfence                      ; both stores visible before I look at yours
.wait:
    cmp dword [flag + rsi*4], 0 ; while you want to AND it's your turn: wait
    je .enter
    cmp [turn], esi
    jne .enter
    pause
    jmp .wait
.enter:
    ret

peterson_unlock:                ; rdi = me
    mov dword [flag + rdi*4], 0
    ret

section .data
msg:   db "both inside: "
msg_n: db "?", 10
MSG_LEN equ $ - msg

section .bss
alignb 64
flag:   resd 2
turn:   resd 1
inside: resd 1
both:   resd 1
go:     resd 1
tids:   resd 2
alignb 16
stacks: resb 3 * 4096
;! witness schedule = 15
