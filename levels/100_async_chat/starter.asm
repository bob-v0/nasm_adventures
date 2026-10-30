; Level 100 — Async Chat Server (boss)
;
; A chat server on 127.0.0.1:7000, built on the game's task runtime:
;
;   - a client's first line is its name; from then on each line it sends goes to every
;     other client as "name: line"
;   - "* name joined" / "* name left" go to everyone else when a client joins or leaves
;   - lines are at most 400 bytes; names at most 31 (longer: cut)
;   - a client that doesn't read must not slow anyone down: if more than 16384 bytes
;     are waiting to be sent to it, kick it ("* name left" to the others) and close it
;   - the game may cancel any `reader` task at any await: treat it like the client
;     leaving
;   - no leaks, no use after free, no socket left open, no task stuck forever
;
; Given: _start, the acceptor (it spawns reader(fd) for each client), the mailboxes
; (mb_recv returns 0 when the task was cancelled while waiting) and the constants
; below. The structs are suggestions: change anything except the name `reader`.
global _start
extern rt_spawn, rt_run, rt_park, rt_unpark, rt_current, rt_cancel
extern rt_await_readable, rt_await_writable, rt_malloc, rt_free

LIMIT       equ 16384           ; bytes queued for one client before it's kicked
MAX_LINE    equ 400
MAX_NAME    equ 31
MAX_MEMBERS equ 64

M_NEXT equ 0                    ; struct msg
M_KIND equ 8
M_FROM equ 16
M_LEN  equ 24
M_TEXT equ 32
K_JOIN    equ 1
K_SAY     equ 2
K_LEAVE   equ 3
K_DELIVER equ 4
K_STOP    equ 5

S_MB      equ 0                 ; struct session: the writer's mailbox (3 qwords)
S_FD      equ 24
S_REFS    equ 32
S_READER  equ 40
S_WRITER  equ 48
S_PENDING equ 56                ; bytes queued for the writer
S_DEAD    equ 64                ; writing failed: drop output
S_KICK    equ 72                ; the room will kick it
S_NAMELEN equ 80
S_NAME    equ 88                ; 32 bytes
S_LINELEN equ 120
S_LINE    equ 128               ; MAX_LINE + 1 bytes
S_SIZE    equ 536

MB_HEAD   equ 0
MB_TAIL   equ 8
MB_WAITER equ 16

section .text
_start:
    mov eax, 13                 ; ignore SIGPIPE: a vanished client gives -EPIPE instead
    mov edi, 13
    lea rsi, [ignore]
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

; ---- yours ---------------------------------------------------------------------------

reader:                         ; rdi = a client's fd
    ; TODO
    ret

room:
    ; TODO
    ret

; ---- mailboxes ---------------------------------------------------------------------------

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

mb_recv:                        ; rdi = mailbox -> rax = msg, or 0 if this task was cancelled
    push rbx
    mov rbx, rdi
.try:
    mov rax, [rbx + MB_HEAD]
    test rax, rax
    jnz .take
    call rt_current
    mov [rbx + MB_WAITER], rax
    call rt_park
    test rax, rax
    jz .try
    mov qword [rbx + MB_WAITER], 0
    xor eax, eax
    jmp .ret
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
ignore: dq 1, 0, 0, 0
addr:   dw 2
        db 7000 >> 8, 7000 & 0xFF
        db 127, 0, 0, 1
        times 8 db 0
star:   db "*", 0
colon:  db ":", 0
joined: db " joined", 10, 0
left:   db " left", 10, 0

section .bss
room_mb:  resq 3
nmembers: resq 1
members:  resq MAX_MEMBERS
out_len:  resq 1
out:      resb MAX_LINE + MAX_NAME + 16
