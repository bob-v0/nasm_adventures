; The game's task runtime (Arc VI, from level 106 on): your level 107 runtime, grown up.
;
;   rt_spawn(fn, arg) -> task       a new ready task running fn(arg)
;   rt_run() -> stuck               run until no task is left; returns how many tasks are
;                                   still waiting with nothing left to wake them (0 = fine)
;   rt_current() -> task
;   rt_yield() -> 0 | -125          let the other ready tasks run first
;   rt_park() -> 0 | -125           sleep until someone calls rt_unpark(this task)
;   rt_unpark(task)                 wake a parked task (does nothing if it isn't parked)
;   rt_sleep(ms) -> 0 | -125
;   rt_await_readable(fd) / rt_await_writable(fd) -> 0 | -125
;   rt_lock(mutex) -> 0 | -125      an async mutex: struct mutex = 3 qwords, zeroed
;   rt_unlock(mutex)
;   rt_cancel(task)                 the task's current or next await returns -125
;                                   (-ECANCELED); so do all its later awaits
;   rt_malloc(size) / rt_free(p)    the game's checked allocator
;
; Every rt_yield/park/sleep/await/lock is an AWAIT POINT: other tasks may run before it
; returns. When several tasks are ready, the game decides which runs next (the grader
; explores many orders), so never rely on the order.

global rt_spawn, rt_run, rt_current, rt_yield, rt_park, rt_unpark, rt_sleep
global rt_await_readable, rt_await_writable, rt_lock, rt_unlock, rt_cancel
global rt_malloc, rt_free

MAX_TASKS  equ 64
STACK_SIZE equ 32768
ECANCELED  equ 125
SYS_RING_MALLOC equ 0x1000
SYS_RING_FREE   equ 0x1001
SYS_RING_CHOOSE equ 0x1002       ; which of n ready tasks runs next
SYS_RING_AWAIT  equ 0x1003       ; an await point: returns 1 if the grader cancels here

; struct task
T_CTX    equ 0                   ; rsp, rbx, rbp, r12..r15
T_FN     equ 56
T_ARG    equ 64
T_STATE  equ 72
T_ID     equ 80
T_CANCEL equ 88
T_WAKE   equ 96                  ; rt_sleep deadline (ns)
T_RESULT equ 104                 ; what the await returns
T_MNEXT  equ 112                 ; next waiter on a mutex
T_SIZE   equ 128

FREE equ 0
READY equ 1
RUNNING equ 2
PARKED equ 3
WAIT_FD equ 4
SLEEPING equ 5
WAIT_LOCK equ 6

; struct mutex
M_OWNER equ 0
M_HEAD  equ 8
M_TAIL  equ 16

section .text

rt_current:
    mov rax, [rt_cur]
    ret

rt_spawn:                        ; rdi = fn, rsi = arg
    lea rax, [rt_tasks]
    xor ecx, ecx
.find:
    cmp ecx, MAX_TASKS
    jae .full
    cmp qword [rax + T_STATE], FREE
    je .found
    add rax, T_SIZE
    inc ecx
    jmp .find
.full:
    xor eax, eax
    ret
.found:
    mov [rax + T_FN], rdi
    mov [rax + T_ARG], rsi
    mov qword [rax + T_CANCEL], 0
    mov qword [rax + T_WAKE], 0
    inc qword [rt_next_id]
    mov rdx, [rt_next_id]
    mov [rax + T_ID], rdx
    imul rdx, rcx, STACK_SIZE
    lea rdx, [rt_stacks + rdx + STACK_SIZE - 8]
    lea rsi, [rt__start]
    mov [rdx], rsi
    mov [rax + T_CTX], rdx
    mov [rax + T_CTX + 8], rax   ; rbx = the task
    inc qword [rt_live]
    push rax
    mov rdi, rax
    call rt__ready
    pop rax
    ret

rt__start:                       ; rbx = the task
    mov rdi, [rbx + T_ARG]
    call [rbx + T_FN]
    mov qword [rbx + T_STATE], FREE
    dec qword [rt_live]
    lea rdi, [rt_dead_ctx]
    lea rsi, [rt_main_ctx]
    call rt__switch              ; never returns

rt__ready:                       ; rdi = task: append to the ready list
    mov qword [rdi + T_STATE], READY
    mov rax, [rt_nready]
    mov [rt_ready + rax*8], rdi
    inc qword [rt_nready]
    ret

rt__switch:                      ; co_switch: save into *rdi, load from *rsi
    mov [rdi], rsp
    mov [rdi + 8], rbx
    mov [rdi + 16], rbp
    mov [rdi + 24], r12
    mov [rdi + 32], r13
    mov [rdi + 40], r14
    mov [rdi + 48], r15
    mov rsp, [rsi]
    mov rbx, [rsi + 8]
    mov rbp, [rsi + 16]
    mov r12, [rsi + 24]
    mov r13, [rsi + 32]
    mov r14, [rsi + 40]
    mov r15, [rsi + 48]
    ret

rt__checkpoint:                  ; the start of every await: rax = 0, or -125 if cancelled
    mov rdx, [rt_cur]
    mov eax, SYS_RING_AWAIT
    mov rdi, [rdx + T_ID]
    mov rsi, [rdx + T_FN]        ; (so the grader can pick tasks by their function)
    syscall
    mov rdx, [rt_cur]
    test rax, rax
    jz .asked
    mov qword [rdx + T_CANCEL], 1
.asked:
    xor eax, eax
    cmp qword [rdx + T_CANCEL], 0
    je .ok
    mov rax, -ECANCELED
.ok:
    ret

rt__suspend:                     ; state already set: switch to the loop; rax = T_RESULT
    mov rdi, [rt_cur]
    mov qword [rdi + T_RESULT], 0
    lea rsi, [rt_main_ctx]
    call rt__switch
    mov rax, [rt_cur]
    mov rax, [rax + T_RESULT]
    ret

rt_yield:
    call rt__checkpoint
    test rax, rax
    jnz .ret
    mov rdi, [rt_cur]
    call rt__ready
    call rt__suspend
.ret:
    ret

rt_park:
    call rt__checkpoint
    test rax, rax
    jnz .ret
    mov rdi, [rt_cur]
    mov qword [rdi + T_STATE], PARKED
    call rt__suspend
.ret:
    ret

rt_unpark:                       ; rdi = task
    cmp qword [rdi + T_STATE], PARKED
    jne .ret
    jmp rt__ready
.ret:
    ret

rt_cancel:                       ; rdi = task
    cmp qword [rdi + T_STATE], FREE
    je .ret
    mov qword [rdi + T_CANCEL], 1
    mov rax, [rdi + T_STATE]
    cmp rax, PARKED
    jb .ret                      ; ready or running: its next await sees the flag
    cmp rax, WAIT_FD
    jne .wake
    dec qword [rt_io_waiting]
.wake:
    push rdi
    call rt__ready
    pop rdi
    mov qword [rdi + T_RESULT], -ECANCELED
.ret:
    ret

rt_sleep:                        ; rdi = ms
    push rbx
    mov rbx, rdi
    call rt__checkpoint
    test rax, rax
    jnz .ret
    call rt__now
    imul rbx, rbx, 1000000
    add rax, rbx
    mov rdi, [rt_cur]
    mov [rdi + T_WAKE], rax
    mov qword [rdi + T_STATE], SLEEPING
    call rt__suspend
.ret:
    pop rbx
    ret

rt_await_readable:               ; rdi = fd
    mov esi, 1 | (1 << 30)       ; EPOLLIN | EPOLLONESHOT
    jmp rt__await_fd
rt_await_writable:
    mov esi, 4 | (1 << 30)       ; EPOLLOUT | EPOLLONESHOT
rt__await_fd:
    push rbx
    push r12
    sub rsp, 24
    mov rbx, rdi
    mov r12, rsi
    call rt__checkpoint
    test rax, rax
    jnz .ret
    call rt__epoll
    mov [rsp], r12d              ; struct epoll_event (packed) on the stack
    mov rax, [rt_cur]
    mov [rsp + 4], rax
    mov eax, 233                 ; epoll_ctl(ep, MOD, fd, &ev); ADD if it's new
    mov rdi, [rt_ep]
    mov esi, 3
    mov rdx, rbx
    mov r10, rsp
    syscall
    cmp rax, -2
    jne .wait
    mov eax, 233
    mov rdi, [rt_ep]
    mov esi, 1
    mov rdx, rbx
    mov r10, rsp
    syscall
.wait:
    mov rdi, [rt_cur]
    mov qword [rdi + T_STATE], WAIT_FD
    inc qword [rt_io_waiting]
    call rt__suspend
.ret:
    add rsp, 24
    pop r12
    pop rbx
    ret

rt_lock:                         ; rdi = mutex
    push rbx
    mov rbx, rdi
    call rt__checkpoint
    test rax, rax
    jnz .ret
    mov rdx, [rt_cur]
    cmp qword [rbx + M_OWNER], 0
    jne .wait
    mov [rbx + M_OWNER], rdx
    jmp .ret
.wait:                           ; join the queue
    mov qword [rdx + T_MNEXT], 0
    mov rax, [rbx + M_TAIL]
    test rax, rax
    jz .first
    mov [rax + T_MNEXT], rdx
    jmp .queued
.first:
    mov [rbx + M_HEAD], rdx
.queued:
    mov [rbx + M_TAIL], rdx
    mov qword [rdx + T_STATE], WAIT_LOCK
    call rt__suspend
    test rax, rax
    jz .ret                      ; rt_unlock handed us the lock
    mov rdx, [rt_cur]            ; cancelled while waiting: leave the queue
    lea rcx, [rbx + M_HEAD]      ; rcx = address of the link that points at us
    xor r8d, r8d                 ; the previous waiter
.scan:
    mov rdi, [rcx]
    test rdi, rdi
    jz .ret
    cmp rdi, rdx
    je .unlink
    mov r8, rdi
    lea rcx, [rdi + T_MNEXT]
    jmp .scan
.unlink:
    mov rdi, [rdx + T_MNEXT]
    mov [rcx], rdi
    cmp [rbx + M_TAIL], rdx
    jne .ret
    mov [rbx + M_TAIL], r8
.ret:
    pop rbx
    ret

rt_unlock:                       ; rdi = mutex
    mov rax, [rdi + M_HEAD]
    test rax, rax
    jz .free
    mov rdx, [rax + T_MNEXT]     ; hand the lock straight to the first waiter
    mov [rdi + M_HEAD], rdx
    test rdx, rdx
    jnz .give
    mov qword [rdi + M_TAIL], 0
.give:
    cmp qword [rax + T_STATE], WAIT_LOCK
    jne rt_unlock                ; cancelled meanwhile: it isn't waiting any more
    mov [rdi + M_OWNER], rax
    mov rdi, rax
    jmp rt__ready
.free:
    mov qword [rdi + M_OWNER], 0
    ret

rt_malloc:
    mov eax, SYS_RING_MALLOC
    syscall
    ret

rt_free:
    mov eax, SYS_RING_FREE
    syscall
    ret

rt__now:                         ; rax = CLOCK_MONOTONIC, ns
    sub rsp, 24
    mov eax, 228
    mov edi, 1
    mov rsi, rsp
    syscall
    imul rax, [rsp], 1000000000
    add rax, [rsp + 8]
    add rsp, 24
    ret

rt__epoll:                       ; create the epoll fd on first use
    cmp qword [rt_ep], 0
    jne .ret
    mov eax, 291
    xor edi, edi
    syscall
    mov [rt_ep], rax
.ret:
    ret

rt_run:
    push rbx
    push r12
    push r13
    push r14
.loop:
    mov rcx, [rt_nready]
    test rcx, rcx
    jz .idle
    mov rdi, rcx                 ; i = the game's choice among the ready tasks
    mov eax, SYS_RING_CHOOSE
    syscall
    cmp rax, [rt_nready]
    jb .chosen
    xor eax, eax
.chosen:
    mov rbx, [rt_ready + rax*8]
.remove:                         ; close the gap, keeping the order
    lea rcx, [rax + 1]
    cmp rcx, [rt_nready]
    jae .removed
    mov rdx, [rt_ready + rcx*8]
    mov [rt_ready + rax*8], rdx
    inc rax
    jmp .remove
.removed:
    dec qword [rt_nready]
    mov [rt_cur], rbx
    mov qword [rbx + T_STATE], RUNNING
    lea rdi, [rt_main_ctx]
    mov rsi, rbx
    call rt__switch
    jmp .loop

.idle:                           ; nothing ready: wait for I/O or a sleeper
    cmp qword [rt_live], 0
    je .done
    mov r12, -1                  ; the earliest sleeper's deadline
    lea rbx, [rt_tasks]
    mov ecx, MAX_TASKS
.sleepers:
    cmp qword [rbx + T_STATE], SLEEPING
    jne .not_sleeping
    mov rax, [rbx + T_WAKE]
    cmp rax, r12
    jae .not_sleeping
    mov r12, rax
.not_sleeping:
    add rbx, T_SIZE
    dec ecx
    jnz .sleepers
    mov r13, -1                  ; epoll timeout (ms): -1 = no sleeper
    cmp r12, -1
    je .poll
    call rt__now
    mov r13, r12
    sub r13, rax
    jbe .due                     ; already due: don't wait at all
    add r13, 999999              ; ns -> ms, rounded up
    mov rax, r13
    xor edx, edx
    mov ecx, 1000000
    div rcx
    mov r13, rax
    jmp .poll
.due:
    xor r13d, r13d
.poll:
    cmp r13, -1
    jne .epoll_wait
    cmp qword [rt_io_waiting], 0
    je .stuck                    ; nothing can ever wake anyone
.epoll_wait:
    call rt__epoll
    mov eax, 232
    mov rdi, [rt_ep]
    lea rsi, [rt_events]
    mov edx, 64
    mov r10, r13
    syscall
    xor r14d, r14d
.event:
    cmp r14, rax
    jae .wake_sleepers
    imul rcx, r14, 12
    mov rdi, [rt_events + rcx + 4]
    inc r14
    cmp qword [rdi + T_STATE], WAIT_FD
    jne .event                   ; stale (it was cancelled meanwhile)
    dec qword [rt_io_waiting]
    push rax
    call rt__ready
    pop rax
    jmp .event
.wake_sleepers:
    call rt__now
    mov r12, rax
    lea rbx, [rt_tasks]
    mov r14d, MAX_TASKS
.wake:
    cmp qword [rbx + T_STATE], SLEEPING
    jne .next_sleeper
    cmp [rbx + T_WAKE], r12
    ja .next_sleeper
    mov rdi, rbx
    call rt__ready
.next_sleeper:
    add rbx, T_SIZE
    dec r14d
    jnz .wake
    jmp .loop

.stuck:                          ; tasks remain, all parked or waiting for locks
    mov eax, 1
    mov edi, 2
    lea rsi, [rt_stuck_msg]
    mov edx, RT_STUCK_LEN
    syscall
    mov rax, [rt_live]
    jmp .out
.done:
    xor eax, eax
.out:
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

section .data
rt_stuck_msg: db "rt: tasks are waiting forever: nothing will ever wake them", 10
RT_STUCK_LEN equ $ - rt_stuck_msg

section .bss
rt_cur:        resq 1
rt_next_id:    resq 1
rt_live:       resq 1
rt_nready:     resq 1
rt_io_waiting: resq 1
rt_ep:         resq 1
rt_main_ctx:   resq 7
rt_dead_ctx:   resq 7
rt_ready:      resq MAX_TASKS
rt_events:     resb 12 * 64
alignb 16
rt_tasks:      resb T_SIZE * MAX_TASKS
alignb 16
rt_stacks:     resb STACK_SIZE * MAX_TASKS
