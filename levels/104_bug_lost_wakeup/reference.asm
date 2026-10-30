; Level 104 — Lost Wakeup (reference)
;
; Level 106's channel, with one improvement: when a receiver finds the channel empty,
; it first records that it went idle in the statistics service (an await), then waits.
; Since then, consumers sometimes sleep forever: the runtime reports tasks "waiting
; forever" and values are never received.
;
; 1. Find a schedule that loses a wakeup:   ;! witness schedule = N
; 2. Fix it.
global chan_init, chan_send, chan_recv, chan_close
extern rt_park, rt_unpark, rt_current, rt_yield

; struct channel (in 4096 zeroed bytes the harness gives you)
CAP     equ 0
HEAD    equ 8
COUNT   equ 16
CLOSED  equ 24
NSEND   equ 32                  ; tasks waiting to send (a queue of wakers)
NRECV   equ 40
SENDERS equ 48                  ; 64 task pointers
RECVERS equ 48 + 512
BUF     equ 48 + 1024           ; up to 64 values

section .text
chan_init:                      ; rdi = channel, rsi = capacity (1..64)
    mov [rdi + CAP], rsi
    ret

chan_send:                      ; rdi = channel, rsi = value
    push rbx
    push r12
    sub rsp, 8
    mov rbx, rdi
    mov r12, rsi
.try:
    mov rax, [rbx + COUNT]
    cmp rax, [rbx + CAP]
    jb .room
    lea rdi, [rbx + SENDERS]    ; full: wait to be woken by a receiver, then look again
    lea rsi, [rbx + NSEND]
    call wait_in
    jmp .try
.room:
    add rax, [rbx + HEAD]       ; buf[(head + count) % cap] = value
    xor edx, edx
    div qword [rbx + CAP]
    mov [rbx + BUF + rdx*8], r12
    inc qword [rbx + COUNT]
    lea rdi, [rbx + RECVERS]    ; a receiver may be waiting for exactly this
    lea rsi, [rbx + NRECV]
    call wake_one
    xor eax, eax
    add rsp, 8
    pop r12
    pop rbx
    ret

chan_recv:                      ; rdi = channel -> rax = value, rdx = 1; rdx = 0: closed
    push rbx
    push r12
    sub rsp, 8
    mov rbx, rdi
.try:
    cmp qword [rbx + COUNT], 0
    jne .take
    xor edx, edx
    cmp qword [rbx + CLOSED], 0
    jne .out
    call note_idle              ; statistics: this consumer is idle (an await)
    cmp qword [rbx + COUNT], 0  ; the await let others run: check AGAIN before parking
    jne .take
    cmp qword [rbx + CLOSED], 0
    jne .try
    lea rdi, [rbx + RECVERS]
    lea rsi, [rbx + NRECV]
    call wait_in
    jmp .try
.take:
    mov rax, [rbx + HEAD]
    mov r12, [rbx + BUF + rax*8]
    inc rax
    xor edx, edx
    div qword [rbx + CAP]
    mov [rbx + HEAD], rdx
    dec qword [rbx + COUNT]
    lea rdi, [rbx + SENDERS]    ; room for one more: wake a waiting sender
    lea rsi, [rbx + NSEND]
    call wake_one
    mov rax, r12
    mov edx, 1
.out:
    add rsp, 8
    pop r12
    pop rbx
    ret

chan_close:                     ; rdi = channel: no more values; wake every receiver
    push rbx
    mov rbx, rdi
    mov qword [rbx + CLOSED], 1
.wake:
    cmp qword [rbx + NRECV], 0
    je .done
    lea rdi, [rbx + RECVERS]
    lea rsi, [rbx + NRECV]
    call wake_one
    jmp .wake
.done:
    pop rbx
    ret

note_idle:                      ; the statistics service is another task: an await point
    sub rsp, 8
    inc qword [idle_count]
    call rt_yield
    add rsp, 8
    ret

wait_in:                        ; rdi = queue, rsi = &count: register as waker, then park
    sub rsp, 8
    mov rcx, [rsi]
    inc qword [rsi]
    push rdi
    push rcx
    call rt_current
    pop rcx
    pop rdi
    mov [rdi + rcx*8], rax
    call rt_park
    add rsp, 8
    ret

wake_one:                       ; rdi = queue, rsi = &count: unpark the first waiter
    mov rcx, [rsi]
    test rcx, rcx
    jz .none
    push rdi
    mov rax, [rdi]              ; the first, then shift the rest down
    dec qword [rsi]
    mov rcx, [rsi]
    xor edx, edx
.shift:
    cmp rdx, rcx
    jae .shifted
    mov r8, [rdi + rdx*8 + 8]
    mov [rdi + rdx*8], r8
    inc rdx
    jmp .shift
.shifted:
    pop rdi
    mov rdi, rax
    jmp rt_unpark
.none:
    ret

section .bss
idle_count: resq 1
;! witness schedule = 3
