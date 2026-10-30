; Level 107 — Tasks & Await (reference)
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

spawn:                          ; rdi = fn, rsi = arg: a new ready task running fn(arg)
    lea rax, [tasks]
    xor ecx, ecx
.find:
    cmp ecx, MAX_TASKS
    jae .full
    cmp qword [rax + USED], 0
    je .found
    add rax, TASK
    inc ecx
    jmp .find
.found:
    mov qword [rax + USED], 1
    mov [rax + FN], rdi
    mov [rax + ARG], rsi
    imul rdx, rcx, STACK_SIZE   ; its stack: the top of stack slot ecx
    lea rdx, [stacks + rdx + STACK_SIZE - 8]
    lea rsi, [task_start]
    mov [rdx], rsi              ; co_switch's ret will "return" to task_start
    mov [rax + CTX], rdx        ; saved rsp
    mov [rax + CTX + 8], rax    ; saved rbx = the task itself
    mov rdi, rax
    jmp make_ready
.full:
    ret

task_start:                     ; first switch into a task lands here; rbx = the task
    mov rdi, [rbx + ARG]
    call [rbx + FN]
    mov qword [rbx + USED], 0   ; finished: free the slot (its stack is still in use until
    lea rdi, [dead_ctx]         ; the switch below, which never comes back)
    lea rsi, [main_ctx]
    call co_switch

make_ready:                     ; rdi = task: append to the run queue
    mov qword [rdi + NEXT], 0
    mov rax, [run_tail]
    test rax, rax
    jz .empty
    mov [rax + NEXT], rdi
    mov [run_tail], rdi
    ret
.empty:
    mov [run_head], rdi
    mov [run_tail], rdi
    ret

await_readable:                 ; rdi = fd: suspend the current task until fd is readable
    mov rax, [current]
    mov dword [ev], 1 | (1 << 30)    ; EPOLLIN | EPOLLONESHOT: wake once, then re-arm
    mov [ev + 4], rax
    push rdi
    mov eax, 233                ; epoll_ctl(ep, MOD, fd, &ev): already known?
    mov rdx, rdi
    mov rdi, [ep]
    mov esi, 3
    lea r10, [ev]
    syscall
    pop rdx
    cmp rax, -2                 ; ENOENT: first time, ADD it
    jne .wait
    mov eax, 233
    mov rdi, [ep]
    mov esi, 1
    lea r10, [ev]
    syscall
.wait:
    mov rdi, [current]          ; save this task, go back to the loop
    lea rsi, [main_ctx]
    jmp co_switch               ; (a tail call: co_switch returns to our caller later)

run:                            ; the event loop
.ready:
    mov rdi, [run_head]
    test rdi, rdi
    jz .wait
    mov rax, [rdi + NEXT]
    mov [run_head], rax
    test rax, rax
    jnz .switch
    mov qword [run_tail], 0
.switch:
    mov [current], rdi
    mov rsi, rdi
    lea rdi, [main_ctx]
    call co_switch              ; run it until it awaits or ends
    jmp .ready
.wait:
    mov eax, 232                ; epoll_wait(ep, events, 32, -1)
    mov rdi, [ep]
    lea rsi, [events]
    mov edx, 32
    mov r10, -1
    syscall
    xor ebx, ebx
.event:
    cmp rbx, rax
    jae .ready
    imul rcx, rbx, 12
    mov rdi, [events + rcx + 4] ; the task waiting for it
    push rax
    call make_ready
    pop rax
    inc rbx
    jmp .event

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
