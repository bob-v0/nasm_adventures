; Level 73 — Lifetimes Across Actors
;
; Level 74's actor system, now with actors on the heap and reference counts: a sender
; holds a reference while it sends, a queued actor is held by the run queue until its
; worker is done, and the registry holds one until shutdown. The last reference to go
; frees the actor. Under some schedules: use after free, double free, or a leak.
;
; 1. Find such a schedule:   ;! witness schedule = N
; 2. Fix the reference counting.

global _start

WORKERS   equ 3
PRODUCERS equ 3
ACTORS    equ 4
MSGS      equ 20
TOTAL     equ PRODUCERS * MSGS
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000
SYS_MALLOC equ 0x1000
SYS_FREE   equ 0x1001
FUTEX_WAIT equ 0
FUTEX_WAKE equ 1
; struct actor (128 bytes, zeroed): +0 and +8 are yours (a mailbox, a "scheduled" flag...)
MAILBOX   equ 0                 ; the runtime's (level 74): a stack of messages
SCHEDULED equ 8                 ; 1 while queued or running
A_REFS    equ 16                ; the reference count
A_RUNNING equ 64                ; the harness's: is it running right now?
A_LAST    equ 72                ; last sequence seen from each sender (3 qwords)
A_SIZE    equ 128

section .text
_start:
    xor ebx, ebx                ; create the actors: one reference each, the registry's
.create:
    mov edi, A_SIZE
    mov eax, SYS_MALLOC
    syscall
    mov qword [rax + A_REFS], 1
    mov [actor_ptrs + rbx*8], rax
    inc ebx
    cmp ebx, ACTORS
    jb .create
    xor ebx, ebx
.spawn:
    cmp ebx, WORKERS + PRODUCERS
    je .join
    mov r12, rbx
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
    jz thread
    inc ebx
    jmp .spawn
.join:
    xor ebx, ebx
.next:
    cmp ebx, WORKERS + PRODUCERS
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
    xor ebx, ebx                ; shutdown: the registry lets go of every actor
.release:
    mov rdi, [actor_ptrs + rbx*8]
    call put_ref
    inc ebx
    cmp ebx, ACTORS
    jb .release
    mov eax, 231
    xor edi, edi
    syscall

thread:
    cmp r12, WORKERS
    jb worker
producer:                       ; r12 - WORKERS = sender number
    sub r12, WORKERS
    xor r13d, r13d              ; sequence
.send:
    mov edi, 16
    mov eax, SYS_MALLOC
    syscall
    mov rcx, r12
    shl rcx, 16
    or rcx, r13
    mov [rax + 8], rcx          ; value
    mov qword [rax], 0
    mov rsi, rax
    mov r14, rax
    lea rax, [r12 + r13]        ; to actor (sender + seq) % ACTORS
    and eax, ACTORS - 1
    mov r15, [actor_ptrs + rax*8]
    mov rdi, r15                ; hold a reference while sending
    call get_ref
    mov rdi, r15
    mov rsi, r14
    call actor_send
    mov rdi, r15
    call put_ref
    inc r13
    cmp r13, MSGS
    jb .send
    jmp exit_thread

worker:
    call runq_pop
    test rax, rax
    jz exit_thread              ; stopped
    mov rbx, rax
    mov rdi, rax
    call actor_run
    mov rdi, rbx                ; the run queue's reference: done with it
    call put_ref
    jmp worker
exit_thread:
    mov eax, 60
    xor edi, edi
    syscall

behavior:                       ; rdi = actor, rsi = message (now the actor's: freed here)
    push rbx
    push r12
    sub rsp, 8
    mov rbx, rdi
    mov r12, rsi
    mov eax, 1                  ; mark it running; it mustn't be already
    xchg eax, [rbx + A_RUNNING]
    test eax, eax
    jz .alone
    lock inc dword [problems + 0]
.alone:
    mov rax, [r12 + 8]          ; sender, sequence: in order?
    mov rcx, rax
    shr rcx, 16
    and eax, 0xFFFF
    inc eax                     ; (stored as sequence + 1)
    cmp eax, [rbx + A_LAST + rcx*8]
    ja .ordered
    lock inc dword [problems + 4]
.ordered:
    mov [rbx + A_LAST + rcx*8], eax
    mov dword [rbx + A_RUNNING], 0
    mov rdi, r12
    mov eax, SYS_FREE
    syscall
    mov eax, 1                  ; count it; the last one stops the workers
    lock xadd [processed], eax
    inc eax
    cmp eax, TOTAL
    jne .out
    call runq_stop
.out:
    add rsp, 8
    pop r12
    pop rbx
    ret

; ---- the actor runtime (level 74's) --------------------------------------------------

actor_send:                     ; rdi = actor, rsi = message
    push rbx
    mov rbx, rdi
    mov rax, [rbx + MAILBOX]    ; push it (lock-free: many senders)
.push:
    mov [rsi], rax
    lock cmpxchg [rbx + MAILBOX], rsi
    jnz .push
    mov eax, 1                  ; schedule the actor, unless it already is
    xchg eax, [rbx + SCHEDULED]
    test eax, eax
    jnz .done
    mov rdi, rbx
    call runq_push
.done:
    pop rbx
    ret

actor_run:                      ; rdi = actor (we're its only runner)
    push rbx
    push r12
    push r13
    mov rbx, rdi
.batch:
    xor eax, eax                ; take everything (one consumer: an xchg is enough)
    xchg rax, [rbx + MAILBOX]
    xor r12d, r12d              ; reverse it: oldest first
.reverse:
    test rax, rax
    jz .reversed
    mov rcx, [rax]
    mov [rax], r12
    mov r12, rax
    mov rax, rcx
    jmp .reverse
.reversed:
    test r12, r12
    jz .idle
.each:
    mov r13, [r12]              ; (behavior frees the message: read next first)
    mov rdi, rbx
    mov rsi, r12
    call behavior
    mov r12, r13
    test r12, r12
    jnz .each
    jmp .batch
.idle:
    mov dword [rbx + SCHEDULED], 0
    mfence                      ; the flag must be visible before we look at the mailbox
    cmp qword [rbx + MAILBOX], 0
    je .out                     ; nothing came: a sender will schedule us again
    mov eax, 1                  ; something came in meanwhile: take it back, unless a
    xchg eax, [rbx + SCHEDULED] ; sender already rescheduled us
    test eax, eax
    jz .batch
.out:
    pop r13
    pop r12
    pop rbx
    ret

; ---- reference counts -------------------------------------------------------------------

get_ref:                        ; rdi = actor: one more reference
    inc qword [rdi + A_REFS]
    ret

put_ref:                        ; rdi = actor: one reference less; the last one frees it
    dec qword [rdi + A_REFS]
    cmp qword [rdi + A_REFS], 0
    jne .alive
    mov eax, SYS_FREE
    syscall
.alive:
    ret

; ---- the run queue: actors waiting for a worker (a mutex + a futex) -------------------

runq_push:                      ; rdi = actor: queued, it's held by the run queue
    push rbx
    mov rbx, rdi
    call get_ref
    lea rdi, [rq_lock]
    call mutex_lock
    mov rax, [rq_tail]
    and eax, 63
    mov [rq + rax*8], rbx
    inc qword [rq_tail]
    lock inc dword [rq_seq]
    lea rdi, [rq_lock]
    call mutex_unlock
    mov eax, 202
    lea rdi, [rq_seq]
    mov esi, FUTEX_WAKE
    mov edx, 1
    syscall
    pop rbx
    ret

runq_pop:                       ; -> rax = an actor, or 0 once stopped
    push rbx
.again:
    lea rdi, [rq_lock]
    call mutex_lock
    mov rax, [rq_head]
    cmp rax, [rq_tail]
    jne .take
    mov ebx, [rq_seq]           ; empty: sleep until something's pushed (or stop)
    cmp dword [rq_stop], 0
    jne .stopped
    lea rdi, [rq_lock]
    call mutex_unlock
    mov eax, 202
    lea rdi, [rq_seq]
    mov esi, FUTEX_WAIT
    mov edx, ebx
    xor r10d, r10d
    syscall
    jmp .again
.take:
    and eax, 63
    mov rbx, [rq + rax*8]
    inc qword [rq_head]
    lea rdi, [rq_lock]
    call mutex_unlock
    mov rax, rbx
    pop rbx
    ret
.stopped:
    lea rdi, [rq_lock]
    call mutex_unlock
    xor eax, eax
    pop rbx
    ret

runq_stop:
    lea rdi, [rq_lock]
    call mutex_lock
    mov dword [rq_stop], 1
    lock inc dword [rq_seq]
    lea rdi, [rq_lock]
    call mutex_unlock
    mov eax, 202
    lea rdi, [rq_seq]
    mov esi, FUTEX_WAKE
    mov edx, 0x7FFFFFFF
    syscall
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

section .bss
alignb 64
actor_ptrs: resq ACTORS
problems:  resd 16              ; [0] ran on two workers at once, [1] out of order
processed: resd 16
rq_lock:   resd 16
rq_seq:    resd 16
rq_stop:   resd 16
rq_head:   resq 8
rq_tail:   resq 8
rq:        resq 64
tids:      resd 8
alignb 16
stacks:    resb 8 * 8192
