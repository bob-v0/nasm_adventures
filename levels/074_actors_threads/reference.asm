; Level 74 — Actors Across Threads (reference)
global actor_send, actor_run
extern runq_push, behavior

MAILBOX   equ 0                 ; a Treiber stack of messages (newest first)
SCHEDULED equ 8                 ; 1 while the actor is queued or running

section .text
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
