; Level 107 — Tasks & Await
;
; Level 109's echo server, rewritten as TASKS: `acceptor` and `client` below are plain
; straight-line code that calls await_readable(fd) wherever it would have to wait.
; They're done. Write the runtime that makes them work:
;
;   spawn(fn, arg)       a new task with its own stack, ready to run fn(arg)
;   await_readable(fd)   suspend the current task until fd is readable
;   run                  the event loop: run ready tasks; when none is ready,
;                        epoll_wait and make the tasks whose fds are ready, ready
;
; co_switch(save, load) from level 129 is provided (extern).
global _start
extern co_switch

MAX_TASKS  equ 64
STACK_SIZE equ 16384
; struct task
CTX   equ 0                     ; 56 bytes: rsp, rbx, rbp, r12..r15 (co_switch's layout)
NEXT  equ 56                    ; run queue link
FN    equ 64
ARG   equ 72
USED  equ 80
TASK  equ 88                    ; sizeof(struct task)

section .text
_start:
    mov eax, 291                ; epoll_create1(0)
    xor edi, edi
    syscall
    mov [ep], rax
    lea rdi, [acceptor]
    xor esi, esi
    call spawn
    call run                    ; never returns while there's work

; ---- the tasks: straight-line code, given ------------------------------------------

acceptor:                       ; listen on 127.0.0.1:7000, start a client task per connection
    push rbx
    mov eax, 41
    mov edi, 2
    mov esi, 1 | 0o4000         ; non-blocking: a task never blocks the whole thread
    xor edx, edx
    syscall
    mov rbx, rax
    mov eax, 49
    mov rdi, rbx
    lea rsi, [addr]
    mov edx, 16
    syscall
    mov eax, 50
    mov rdi, rbx
    mov esi, 64
    syscall
.next:
    mov rdi, rbx
    call await_readable         ; suspend until a client is connecting
    mov eax, 288                ; accept4(fd, 0, 0, SOCK_NONBLOCK)
    mov rdi, rbx
    xor esi, esi
    xor edx, edx
    mov r10d, 0o4000
    syscall
    test rax, rax
    js .next
    lea rdi, [client]
    mov rsi, rax
    call spawn
    jmp .next

client:                         ; rdi = the connection: echo until the client leaves
    push rbx
    sub rsp, 4096 + 8           ; a buffer on this task's own stack (rsp stays aligned)
    mov rbx, rdi
.more:
    mov rdi, rbx
    call await_readable
    xor eax, eax
    mov rdi, rbx
    mov rsi, rsp
    mov edx, 4096
    syscall
    cmp rax, -11
    je .more
    test rax, rax
    jle .done
    mov rdx, rax
    mov eax, 1
    mov rdi, rbx
    mov rsi, rsp
    syscall
    jmp .more
.done:
    mov eax, 3
    mov rdi, rbx
    syscall
    add rsp, 4096 + 8
    pop rbx
    ret                         ; the task ends

; ---- the runtime: yours -------------------------------------------------------------

spawn:                          ; rdi = fn, rsi = arg
    ; TODO
    ret

await_readable:                 ; rdi = fd
    ; TODO
    ret

run:
    ; TODO
    mov eax, 60
    xor edi, edi
    syscall

section .data
addr: dw 2
      db 7000 >> 8, 7000 & 0xFF
      db 127, 0, 0, 1
      times 8 db 0

section .bss
ep:       resq 1
current:  resq 1
run_head: resq 1
run_tail: resq 1
main_ctx: resq 7
dead_ctx: resq 7
ev:       resb 12
events:   resb 12 * 32
tasks:    resb TASK * MAX_TASKS
alignb 16
stacks:   resb STACK_SIZE * MAX_TASKS
