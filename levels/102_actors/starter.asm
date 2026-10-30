; Level 102 — Actors
;
; A chat room on 127.0.0.1:7000: whatever a client sends goes to every OTHER client in
; the room. Built from actors, tasks that share nothing and talk only through mailboxes:
;
;   reader (one per client, given)  reads its socket, sends JOIN / SAY / LEAVE messages
;   room   (yours)                  owns the member list and every member's socket:
;                                   JOIN: add the fd; SAY: write the text to every
;                                   member except the sender; LEAVE: remove and close it
;
; Messages are heap blocks (rt_malloc). mb_send hands one over: from then on it belongs
; to the receiver, which frees it when it's done with it.
; Write mb_send, mb_recv (one receiver per mailbox: it parks when the mailbox is empty)
; and the room.
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

mb_send:                        ; rdi = mailbox, rsi = msg
    ; TODO
    ret

mb_recv:                        ; rdi = mailbox -> rax = msg
    ; TODO
    xor eax, eax
    ret

room:
    ; TODO
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
