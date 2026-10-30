; Level 79 — Lost Wakeup II
;
; Level 80's blocking queue, from a codebase where cond_wait was "simplified". Most runs
; are fine. Once in a while a consumer (or producer) sleeps forever: the game reports
; every thread asleep on a futex, with values still in the queue or producers waiting.
;
; 1. Find a schedule that loses a wakeup:   ;! witness schedule = N
; 2. Fix it.
global queue_init, queue_put, queue_get, queue_close
extern mutex_lock, mutex_unlock

FUTEX_WAIT equ 0
FUTEX_WAKE equ 1
; struct queue
Q_LOCK      equ 0               ; a mutex
Q_NOT_EMPTY equ 64              ; condition variables: just sequence numbers
Q_NOT_FULL  equ 128
Q_CAP       equ 192
Q_HEAD      equ 200
Q_COUNT     equ 208
Q_CLOSED    equ 216
Q_BUF       equ 256             ; up to 64 values

section .text
queue_init:                     ; rdi = queue, rsi = capacity
    mov [rdi + Q_CAP], rsi
    ret

; A condition variable is a counter. Waiting: unlock, read it, sleep while it's
; unchanged (the futex compares atomically), lock again. Signalling: bump it, wake.
cond_wait:                      ; rdi = cond, rsi = mutex
    push rbx
    push r12
    push r13
    mov rbx, rdi
    mov r12, rsi
    mov rdi, r12
    call mutex_unlock
    mov r13d, [rbx]             ; the sequence number we'll sleep on
    mov eax, 202
    mov rdi, rbx
    mov esi, FUTEX_WAIT
    mov edx, r13d
    xor r10d, r10d
    syscall
    mov rdi, r12
    call mutex_lock
    pop r13
    pop r12
    pop rbx
    ret

cond_signal:                    ; rdi = cond, esi = how many to wake
    lock inc dword [rdi]
    mov edx, esi
    mov eax, 202
    mov esi, FUTEX_WAKE
    syscall
    ret

queue_put:                      ; rdi = queue, rsi = value
    push rbx
    push r12
    sub rsp, 8
    mov rbx, rdi
    mov r12, rsi
    lea rdi, [rbx + Q_LOCK]
    call mutex_lock
.full:                          ; always a loop: wakeups can be spurious, or stale
    mov rax, [rbx + Q_COUNT]
    cmp rax, [rbx + Q_CAP]
    jb .room
    lea rdi, [rbx + Q_NOT_FULL]
    lea rsi, [rbx + Q_LOCK]
    call cond_wait
    jmp .full
.room:
    add rax, [rbx + Q_HEAD]
    xor edx, edx
    div qword [rbx + Q_CAP]
    mov [rbx + Q_BUF + rdx*8], r12
    inc qword [rbx + Q_COUNT]
    lea rdi, [rbx + Q_NOT_EMPTY]
    mov esi, 1
    call cond_signal
    lea rdi, [rbx + Q_LOCK]
    call mutex_unlock
    add rsp, 8
    pop r12
    pop rbx
    ret

queue_get:                      ; rdi = queue -> rax = value, rdx = 1; rdx = 0: closed
    push rbx
    push r12
    sub rsp, 8
    mov rbx, rdi
    lea rdi, [rbx + Q_LOCK]
    call mutex_lock
.empty:
    cmp qword [rbx + Q_COUNT], 0
    jne .take
    cmp qword [rbx + Q_CLOSED], 0
    jne .closed
    lea rdi, [rbx + Q_NOT_EMPTY]
    lea rsi, [rbx + Q_LOCK]
    call cond_wait
    jmp .empty
.take:
    mov rax, [rbx + Q_HEAD]
    mov r12, [rbx + Q_BUF + rax*8]
    inc rax
    xor edx, edx
    div qword [rbx + Q_CAP]
    mov [rbx + Q_HEAD], rdx
    dec qword [rbx + Q_COUNT]
    lea rdi, [rbx + Q_NOT_FULL]
    mov esi, 1
    call cond_signal
    lea rdi, [rbx + Q_LOCK]
    call mutex_unlock
    mov rax, r12
    mov edx, 1
    jmp .out
.closed:
    lea rdi, [rbx + Q_LOCK]
    call mutex_unlock
    xor edx, edx
.out:
    add rsp, 8
    pop r12
    pop rbx
    ret

queue_close:                    ; rdi = queue
    push rbx
    mov rbx, rdi
    lea rdi, [rbx + Q_LOCK]
    call mutex_lock
    mov qword [rbx + Q_CLOSED], 1
    lea rdi, [rbx + Q_NOT_EMPTY]
    mov esi, 0x7FFFFFFF         ; everyone
    call cond_signal
    lea rdi, [rbx + Q_LOCK]
    call mutex_unlock
    pop rbx
    ret
