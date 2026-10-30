; Level 72 — Lock-Free Actor Runtime (reference)
global rt_init, actor_new, actor_send, actor_release, rt_shutdown

MAX_WORKERS equ 8
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000
SYS_MALLOC equ 0x1000
SYS_FREE   equ 0x1001
FUTEX_WAIT equ 0
FUTEX_WAKE equ 1
; struct actor (heap, 32 bytes)
MAILBOX   equ 0                 ; lock-free stack of messages, newest first
SCHEDULED equ 8                 ; 1 while queued or running
REFS      equ 16
BEHAVIOR  equ 24

section .text
; ---- actors ------------------------------------------------------------------------

actor_new:                      ; rdi = behavior -> rax = actor (one reference: the caller's)
    push rbx
    mov rbx, rdi
    mov edi, 32
    mov eax, SYS_MALLOC
    syscall
    mov qword [rax + MAILBOX], 0
    mov qword [rax + SCHEDULED], 0
    mov qword [rax + REFS], 1
    mov [rax + BEHAVIOR], rbx
    pop rbx
    ret

actor_release:                  ; rdi = actor
    jmp put_ref

get_ref:                        ; rdi = actor
    lock inc qword [rdi + REFS]
    ret

put_ref:                        ; rdi = actor: the last reference frees it
    mov rax, -1
    lock xadd [rdi + REFS], rax
    cmp rax, 1
    jne .alive
    mov eax, SYS_FREE
    syscall
.alive:
    ret

actor_send:                     ; rdi = actor, rsi = msg
    push rbx
    mov rbx, rdi
    lock inc qword [inflight]   ; counted until its behavior has run
    mov rax, [rbx + MAILBOX]
.push:
    mov [rsi], rax
    lock cmpxchg [rbx + MAILBOX], rsi
    jnz .push
    mov eax, 1
    xchg eax, [rbx + SCHEDULED]
    test eax, eax
    jnz .done
    mov rdi, rbx
    call runq_push
.done:
    pop rbx
    ret

actor_run:                      ; rdi = actor (one runner at a time)
    push rbx
    push r12
    push r13
    mov rbx, rdi
.batch:
    xor eax, eax
    xchg rax, [rbx + MAILBOX]
    xor r12d, r12d
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
    mov r13, [r12]
    mov rdi, rbx
    mov rsi, r12
    call [rbx + BEHAVIOR]
    mov rax, -1                 ; one message less in flight; the last one wakes shutdown
    lock xadd [inflight], rax
    cmp rax, 1
    jne .more
    mov eax, 202
    lea rdi, [inflight]
    mov esi, FUTEX_WAKE
    mov edx, 1
    syscall
.more:
    mov r12, r13
    test r12, r12
    jnz .each
    jmp .batch
.idle:
    mov dword [rbx + SCHEDULED], 0
    mfence
    cmp qword [rbx + MAILBOX], 0
    je .out
    mov eax, 1
    xchg eax, [rbx + SCHEDULED]
    test eax, eax
    jz .batch
.out:
    pop r13
    pop r12
    pop rbx
    ret

; ---- workers ------------------------------------------------------------------------

rt_init:                        ; rdi = number of workers
    push rbx
    push r12
    sub rsp, 8
    mov [nworkers], rdi
    xor ebx, ebx
.spawn:
    cmp rbx, [nworkers]
    jae .done
    mov eax, 56
    mov edi, CLONE
    lea rsi, [rbx + 1]
    shl rsi, 13
    lea rsi, [wstacks + rsi]
    lea rdx, [wtids + rbx*4]
    mov r10, rdx
    xor r8d, r8d
    syscall
    test rax, rax
    jz worker
    inc ebx
    jmp .spawn
.done:
    add rsp, 8
    pop r12
    pop rbx
    ret

worker:
    call runq_pop
    test rax, rax
    jz .exit
    mov rbx, rax
    mov rdi, rax
    call actor_run
    mov rdi, rbx                ; the run queue's reference
    call put_ref
    jmp worker
.exit:
    mov eax, 60
    xor edi, edi
    syscall

rt_shutdown:                    ; wait until nothing is in flight, then stop and join
    push rbx
.quiet:
    mov rdx, [inflight]
    test rdx, rdx
    jz .stop
    mov eax, 202
    lea rdi, [inflight]
    mov esi, FUTEX_WAIT
    xor r10d, r10d
    syscall
    jmp .quiet
.stop:
    call runq_stop
    xor ebx, ebx
.join:
    cmp rbx, [nworkers]
    jae .joined
.wait:
    mov edx, [wtids + rbx*4]
    test edx, edx
    jz .next
    mov eax, 202
    lea rdi, [wtids + rbx*4]
    xor esi, esi
    xor r10d, r10d
    syscall
    jmp .wait
.next:
    inc rbx
    jmp .join
.joined:
    pop rbx
    ret

; ---- the run queue (a mutex and a futex) ------------------------------------------------

runq_push:                      ; rdi = actor (queued: the queue holds a reference)
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
inflight: resq 8
nworkers: resq 1
rq_lock:  resd 16
rq_seq:   resd 16
rq_stop:  resd 16
rq_head:  resq 8
rq_tail:  resq 8
rq:       resq 64
wtids:    resd MAX_WORKERS
alignb 16
wstacks:  resb (MAX_WORKERS + 1) * 8192
