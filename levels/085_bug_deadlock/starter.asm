; Level 85 — Deadlock
;
; A bank with 3 accounts, each with its own lock (level 87's futex mutex). Three threads
; move money around in a circle: account 0 -> 1, 1 -> 2, 2 -> 0, 30 times each. A
; transfer locks the account it takes from, then the one it gives to.
; It should print "total 300". Usually it never prints anything at all: the game
; stops it and reports a deadlock.
;
; 1. Find such a schedule:   ;! witness schedule = N
; 2. Fix it.

global _start

ROUNDS equ 30
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000
FUTEX_WAIT equ 0
FUTEX_WAKE equ 1

section .text
_start:
    xor ebx, ebx
.spawn:
    cmp ebx, 3
    je .join
    mov r12, rbx                ; thread i moves from account i to account (i + 1) % 3
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
    jz mover
    inc ebx
    jmp .spawn
.join:
    xor ebx, ebx
.next:
    cmp ebx, 3
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
    mov rax, [balance]
    add rax, [balance + 8]
    add rax, [balance + 16]
    mov ecx, 10                 ; three digits
    lea rdi, [msg_n + 2]
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    mov [rdi], dl
    dec rdi
    cmp rdi, msg_n
    jae .digit
    mov eax, 1
    mov edi, 1
    lea rsi, [msg]
    mov edx, MSG_LEN
    syscall
    mov eax, 231
    xor edi, edi
    syscall

mover:                          ; r12 = from; to = (from + 1) % 3
    mov r13d, ROUNDS
    lea r14, [r12 + 1]
    cmp r14, 3
    jb .round
    xor r14d, r14d
.round:
    mov rdi, r12
    mov rsi, r14
    call transfer
    dec r13d
    jnz .round
    mov eax, 60
    xor edi, edi
    syscall

transfer:                       ; rdi = from, rsi = to: move 1
    push rbx
    push r12
    push r13
    mov rbx, rdi
    mov r12, rsi
    lea rdi, [locks + rbx*4]    ; lock the source...
    call mutex_lock
    lea rdi, [locks + r12*4]    ; ...then the destination
    call mutex_lock
    mov rax, [balance + rbx*8]  ; the transfer itself
    dec rax
    mov [balance + rbx*8], rax
    mov rax, [balance + r12*8]
    inc rax
    mov [balance + r12*8], rax
    lea rdi, [locks + r12*4]
    call mutex_unlock
    lea rdi, [locks + rbx*4]
    call mutex_unlock
    pop r13
    pop r12
    pop rbx
    ret

mutex_lock:                     ; rdi = the lock
    xor eax, eax
    mov edx, 1
    lock cmpxchg [rdi], edx     ; 0 -> 1: got it, nobody waiting
    jz .got
    mov edx, 2
    cmp eax, 2
    je .sleep
.mark:
    mov eax, 2
    xchg eax, [rdi]             ; say "someone waits"; if it was free meanwhile, we own it
    test eax, eax
    jz .got
.sleep:
    push rdi
    mov eax, 202                ; futex(m, FUTEX_WAIT, 2, 0): sleep if it's still 2
    mov esi, FUTEX_WAIT
    mov edx, 2
    xor r10d, r10d
    syscall
    pop rdi
    jmp .mark
.got:
    ret

mutex_unlock:                   ; rdi = the lock
    mov eax, -1
    lock xadd [rdi], eax        ; 1 -> 0: nobody waited, done
    cmp eax, 1
    je .done
    mov dword [rdi], 0          ; it was 2: free it and wake one sleeper
    mov eax, 202
    mov esi, FUTEX_WAKE
    mov edx, 1
    syscall
.done:
    ret

section .data
msg:   db "total "
msg_n: db "???", 10
MSG_LEN equ $ - msg
alignb 8
balance: dq 100, 100, 100

section .bss
alignb 64
locks:  resd 3
tids:   resd 4
alignb 16
stacks: resb 4 * 4096
