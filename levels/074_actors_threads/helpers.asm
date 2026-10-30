; Level 74's harness (the game's): an actor system on WORKERS threads.
;   PRODUCERS threads each send MSGS messages to the ACTORS actors (in a fixed pattern),
;   each message a heap block: dq next, dq value (value = sender << 16 | sequence).
;   Your actor_send queues it; the run queue below hands scheduled actors to workers,
;   which call your actor_run; actor_run passes each message to `behavior` (here), which
;   checks the actor isn't running elsewhere and that each sender's messages arrive in
;   order, counts it and frees it. When every message is processed, the workers stop.
global _start, actors, runq_push, behavior, problems, processed
extern actor_send, actor_run

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
A_RUNNING equ 64                ; the harness's: is it running right now?
A_LAST    equ 72                ; last sequence seen from each sender (3 qwords)
A_SIZE    equ 128

section .text
_start:
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
    lea rax, [r12 + r13]        ; to actor (sender + seq) % ACTORS
    and eax, ACTORS - 1
    imul rdi, rax, A_SIZE
    lea rdi, [actors + rdi]
    call actor_send
    inc r13
    cmp r13, MSGS
    jb .send
    jmp exit_thread

worker:
    call runq_pop
    test rax, rax
    jz exit_thread              ; stopped
    mov rdi, rax
    call actor_run
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

; ---- the run queue: actors waiting for a worker (a mutex + a futex) -------------------

runq_push:                      ; rdi = actor
    push rbx
    mov rbx, rdi
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
actors:    resb A_SIZE * ACTORS
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
