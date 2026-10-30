; Level 101 — Actor Lifetimes (reference)
;
; The fix: the ROOM ends a session. Only it knows when the last message for the session
; has been sent, so it sends K_STOP after removing the member; mailboxes are FIFO, so
; K_STOP is the last thing the writer ever receives.
;
; Level 102's chat room, redesigned so that slow clients can't hold up the room: each
; client now has a SESSION (a heap block: a mailbox and the socket) served by two
; actors: a reader (socket -> room) and a writer (its mailbox -> socket). The room
; sends each member a copy of every message (K_DELIVER) instead of writing itself.
;
; When a client disconnects, its reader tells the room (K_LEAVE) and tells its writer to
; stop (K_STOP); the writer frees the session. Under some schedules the service now dies
; with "use after free".
;
; 1. Find such a schedule:   ;! witness schedule = N
; 2. Fix the lifetimes.

global _start
extern rt_spawn, rt_run, rt_park, rt_unpark, rt_current, rt_await_readable
extern rt_malloc, rt_free

M_NEXT equ 0                    ; struct msg
M_KIND equ 8
M_FROM equ 16                   ; the sender's session
M_LEN  equ 24
M_TEXT equ 32
K_JOIN    equ 1
K_SAY     equ 2
K_LEAVE   equ 3
K_DELIVER equ 4
K_STOP    equ 5
S_MB equ 0                      ; struct session: its mailbox (3 qwords), its socket
S_FD equ 24
S_SIZE equ 32
MB_HEAD   equ 0                 ; struct mailbox
MB_TAIL   equ 8
MB_WAITER equ 16
MAX_MEMBERS equ 64

section .text
_start:
    mov eax, 13                 ; rt_sigaction(SIGPIPE, {SIG_IGN}, 0, 8): a client that
    mov edi, 13                 ; hangs up mid-write makes write() fail with -EPIPE
    lea rsi, [ignore]           ; instead of killing the whole server
    xor edx, edx
    mov r10d, 8
    syscall
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

acceptor:
    push rbx
    mov eax, 41
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

reader:                         ; rdi = fd: create the session, then socket -> room
    push rbx
    push r12
    push r13
    mov r13, rdi
    mov edi, S_SIZE
    call rt_malloc
    mov rbx, rax                ; rbx = the session
    mov qword [rbx + MB_HEAD], 0
    mov qword [rbx + MB_TAIL], 0
    mov qword [rbx + MB_WAITER], 0
    mov [rbx + S_FD], r13
    lea rdi, [writer]
    mov rsi, rbx
    call rt_spawn
    lea rdi, [room_mb]
    mov esi, K_JOIN
    call post
.read:
    mov rdi, r13
    call rt_await_readable
    mov edi, 32 + 512
    call rt_malloc
    mov r12, rax
    xor eax, eax
    mov rdi, r13
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
    call mb_send
    jmp .read
.gone:
    mov rdi, r12
    call rt_free
    cmp rax, -11
    je .read
    lea rdi, [room_mb]          ; the client left: tell the room (it stops the writer)
    mov esi, K_LEAVE
    call post
    pop r13
    pop r12
    pop rbx
    ret

writer:                         ; rdi = session: its mailbox -> its socket
    push rbx
    push r12
    sub rsp, 8
    mov rbx, rdi
.next:
    lea rdi, [rbx + S_MB]
    call mb_recv
    mov r12, rax
    cmp qword [r12 + M_KIND], K_STOP
    je .stop
    mov eax, 1                  ; K_DELIVER: write it out
    mov rdi, [rbx + S_FD]
    lea rsi, [r12 + M_TEXT]
    mov rdx, [r12 + M_LEN]
    syscall
    mov rdi, r12
    call rt_free
    jmp .next
.stop:                          ; the end of this session: close and free everything
    mov rdi, r12
    call rt_free
    mov eax, 3
    mov rdi, [rbx + S_FD]
    syscall
    mov rdi, rbx
    call rt_free
    add rsp, 8
    pop r12
    pop rbx
    ret

room:
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
    xor r12d, r12d              ; K_SAY: a copy to every other member's session
.say:
    cmp r12, [nmembers]
    jae .done
    mov r13, [members + r12*8]
    inc r12
    cmp r13, [rbx + M_FROM]
    je .say
    mov edi, 32 + 512
    call rt_malloc
    mov qword [rax + M_KIND], K_DELIVER
    mov rcx, [rbx + M_LEN]
    mov [rax + M_LEN], rcx
    lea rsi, [rbx + M_TEXT]
    lea rdi, [rax + M_TEXT]
    push rax
    rep movsb
    pop rsi
    lea rdi, [r13 + S_MB]
    call mb_send
    jmp .say
.join:
    mov rax, [nmembers]
    mov rcx, [rbx + M_FROM]
    mov [members + rax*8], rcx
    inc qword [nmembers]
    jmp .done
.leave:
    mov rcx, [rbx + M_FROM]
    xor r12d, r12d
.find:
    cmp r12, [nmembers]
    jae .done
    cmp [members + r12*8], rcx
    je .remove
    inc r12
    jmp .find
.remove:
    dec qword [nmembers]
    mov rax, [nmembers]
    mov rdx, [members + rax*8]
    mov [members + r12*8], rdx
    push rbx                    ; no more K_DELIVER for it: now its writer may stop
    mov rbx, rcx
    lea rdi, [rcx + S_MB]
    mov esi, K_STOP
    call post
    pop rbx
.done:
    mov rdi, rbx
    call rt_free
    jmp .next

post:                           ; rdi = mailbox, esi = kind, rbx = the session (M_FROM)
    push rdi
    push rsi
    sub rsp, 8
    mov edi, 32
    call rt_malloc
    add rsp, 8
    pop rsi
    pop rdi
    mov [rax + M_KIND], rsi
    mov [rax + M_FROM], rbx
    mov qword [rax + M_LEN], 0
    mov rsi, rax
    jmp mb_send

mb_send:                        ; rdi = mailbox, rsi = msg
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
    mov rax, [rdi + MB_WAITER]
    test rax, rax
    jz .ret
    mov qword [rdi + MB_WAITER], 0
    mov rdi, rax
    jmp rt_unpark
.ret:
    ret

mb_recv:                        ; rdi = mailbox -> rax = msg
    push rbx
    mov rbx, rdi
.try:
    mov rax, [rbx + MB_HEAD]
    test rax, rax
    jnz .take
    call rt_current
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

section .data
ignore: dq 1, 0, 0, 0           ; struct sigaction: handler = SIG_IGN
addr: dw 2
      db 7000 >> 8, 7000 & 0xFF
      db 127, 0, 0, 1
      times 8 db 0

section .bss
room_mb:  resq 3
nmembers: resq 1
members:  resq MAX_MEMBERS
;! witness schedule = 4
