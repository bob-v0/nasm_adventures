; Level 102 — Actors (reference)
global _start
extern rt_spawn, rt_run, rt_park, rt_unpark, rt_current, rt_await_readable
extern rt_malloc, rt_free

; struct msg (heap: whoever holds the pointer owns it)
M_NEXT equ 0
M_KIND equ 8                    ; K_JOIN / K_SAY / K_LEAVE
M_FROM equ 16                   ; the client's fd
M_LEN  equ 24
M_TEXT equ 32                   ; up to 512 bytes
K_JOIN  equ 1
K_SAY   equ 2
K_LEAVE equ 3
; struct mailbox
MB_HEAD   equ 0
MB_TAIL   equ 8
MB_WAITER equ 16                ; the (single) receiver, parked

MAX_MEMBERS equ 64

section .text
_start:
    lea rdi, [acceptor]
    xor esi, esi
    call rt_spawn
    lea rdi, [room]
    xor esi, esi
    call rt_spawn
    call rt_run
    mov rdi, rax
    mov eax, 60
    syscall

; ---- given: the acceptor and the connection actors --------------------------------

acceptor:
    push rbx
    mov eax, 41                 ; a non-blocking TCP socket on 127.0.0.1:7000
    mov edi, 2
    mov esi, 1 | 0o4000
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
    call rt_await_readable
    mov eax, 288
    mov rdi, rbx
    xor esi, esi
    xor edx, edx
    mov r10d, 0o4000
    syscall
    test rax, rax
    js .next
    lea rdi, [reader]
    mov rsi, rax
    call rt_spawn
    jmp .next

reader:                         ; rdi = a client's fd: turn what it sends into messages
    push rbx
    push r12
    sub rsp, 8
    mov rbx, rdi
    mov edi, K_JOIN
    xor esi, esi
    call post
.read:
    mov rdi, rbx
    call rt_await_readable
    mov edi, 32 + 512           ; read straight into a new message
    call rt_malloc
    mov r12, rax
    xor eax, eax
    mov rdi, rbx
    lea rsi, [r12 + M_TEXT]
    mov edx, 512
    syscall
    test rax, rax
    jle .gone
    mov qword [r12 + M_KIND], K_SAY
    mov [r12 + M_FROM], rbx
    mov [r12 + M_LEN], rax
    lea rdi, [room_mb]
    mov rsi, r12
    call mb_send                ; the message now belongs to the room
    jmp .read
.gone:                          ; -EAGAIN (nothing after all) or the client left
    mov rdi, r12
    call rt_free
    cmp rax, -11
    je .read
    mov edi, K_LEAVE              ; the room closes the fd: it owns it since JOIN
    xor esi, esi
    call post
    add rsp, 8
    pop r12
    pop rbx
    ret

post:                           ; edi = kind (rbx = fd): a message with no text
    push rdi
    mov edi, 32
    call rt_malloc
    pop rdi
    mov [rax + M_KIND], rdi
    mov [rax + M_FROM], rbx
    mov qword [rax + M_LEN], 0
    lea rdi, [room_mb]
    mov rsi, rax
    jmp mb_send

; ---- yours: the mailbox and the room -------------------------------------------------

mb_send:                        ; rdi = mailbox, rsi = msg (ownership moves to the receiver)
    mov qword [rsi + M_NEXT], 0
    mov rax, [rdi + MB_TAIL]
    test rax, rax
    jz .empty
    mov [rax + M_NEXT], rsi
    jmp .linked
.empty:
    mov [rdi + MB_HEAD], rsi
.linked:
    mov [rdi + MB_TAIL], rsi
    mov rax, [rdi + MB_WAITER]  ; wake the receiver if it sleeps
    test rax, rax
    jz .ret
    mov qword [rdi + MB_WAITER], 0
    mov rdi, rax
    jmp rt_unpark
.ret:
    ret

mb_recv:                        ; rdi = mailbox -> rax = the oldest msg (now yours)
    push rbx
    mov rbx, rdi
.try:
    mov rax, [rbx + MB_HEAD]
    test rax, rax
    jnz .take
    call rt_current             ; empty: leave a waker and sleep (no await in between)
    mov [rbx + MB_WAITER], rax
    call rt_park
    jmp .try
.take:
    mov rcx, [rax + M_NEXT]
    mov [rbx + MB_HEAD], rcx
    test rcx, rcx
    jnz .ret
    mov qword [rbx + MB_TAIL], 0
.ret:
    pop rbx
    ret

room:                           ; the only task that touches members[]
    push rbx
    push r12
    push r13
.next:
    lea rdi, [room_mb]
    call mb_recv
    mov rbx, rax
    mov rax, [rbx + M_KIND]
    cmp rax, K_JOIN
    je .join
    cmp rax, K_LEAVE
    je .leave
    xor r12d, r12d              ; SAY: to every member except the sender
.say:
    cmp r12, [nmembers]
    jae .done
    mov rdi, [members + r12*8]
    inc r12
    cmp rdi, [rbx + M_FROM]
    je .say
    mov eax, 1
    lea rsi, [rbx + M_TEXT]
    mov rdx, [rbx + M_LEN]
    syscall
    jmp .say
.join:
    mov rax, [nmembers]
    cmp rax, MAX_MEMBERS
    jae .done
    mov rcx, [rbx + M_FROM]
    mov [members + rax*8], rcx
    inc qword [nmembers]
    jmp .done
.leave:
    mov rcx, [rbx + M_FROM]     ; remove it (the last one fills the hole), then close it
    xor r12d, r12d
.find:
    cmp r12, [nmembers]
    jae .close
    cmp [members + r12*8], rcx
    je .remove
    inc r12
    jmp .find
.remove:
    dec qword [nmembers]
    mov rax, [nmembers]
    mov rdx, [members + rax*8]
    mov [members + r12*8], rdx
.close:
    mov eax, 3
    mov rdi, rcx
    syscall
.done:
    mov rdi, rbx                ; handled: the message dies here
    call rt_free
    jmp .next

section .data
addr: dw 2
      db 7000 >> 8, 7000 & 0xFF
      db 127, 0, 0, 1
      times 8 db 0

section .bss
room_mb:  resq 3
nmembers: resq 1
members:  resq MAX_MEMBERS
