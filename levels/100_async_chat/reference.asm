; Level 100 — Async Chat Server (reference)
;
; Actors: one acceptor, one room, and per client a reader and a writer sharing a session.
; A session is freed by whichever of its reader and writer finishes last (a refcount of
; 2); the room only ever touches sessions that are members, and a writer only stops
; after the room has removed its session (K_STOP, or a cancel when kicked).
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

; ---- reader: socket -> lines -> the room ---------------------------------------------

reader:                         ; rdi = fd
    push rbx
    push r12
    push r13
    push r14
    sub rsp, 512 + 8
    mov r13, rdi
    mov edi, S_SIZE
    call rt_malloc
    mov rbx, rax
    xor ecx, ecx
.zero:
    mov qword [rbx + rcx], 0
    add ecx, 8
    cmp ecx, S_SIZE
    jb .zero
    mov [rbx + S_FD], r13
    mov qword [rbx + S_REFS], 2 ; the reader and the writer
    call rt_current
    mov [rbx + S_READER], rax
    lea rdi, [writer]
    mov rsi, rbx
    call rt_spawn
    mov [rbx + S_WRITER], rax
.read:
    mov rdi, r13
    call rt_await_readable
    test rax, rax
    js .end                     ; cancelled: like the client leaving
    xor eax, eax
    mov rdi, r13
    mov rsi, rsp
    mov edx, 512
    syscall
    cmp rax, -11
    je .read
    test rax, rax
    jle .end
    mov r12, rax
    xor r14d, r14d
.byte:
    cmp r14, r12
    jae .read
    movzx eax, byte [rsp + r14]
    inc r14
    mov rcx, [rbx + S_LINELEN]
    cmp al, 10
    je .store
    cmp rcx, MAX_LINE
    jae .byte                   ; too long: drop the rest of the line
.store:
    mov [rbx + S_LINE + rcx], al
    inc qword [rbx + S_LINELEN]
    cmp al, 10
    jne .byte
    call line_done
    jmp .byte
.end:
    cmp qword [rbx + S_NAMELEN], 0
    jne .leave
    mov edi, 32                 ; never joined: the room doesn't know us, stop our writer
    call rt_malloc
    mov qword [rax + M_KIND], K_STOP
    lea rdi, [rbx + S_MB]
    mov rsi, rax
    call mb_send
    jmp .release
.leave:
    mov edi, K_LEAVE
    call post
.release:
    mov rdi, rbx
    call release
    add rsp, 512 + 8
    pop r14
    pop r13
    pop r12
    pop rbx
    ret

line_done:                      ; rbx = session: a complete line (with its newline)
    push r12
    mov r12, [rbx + S_LINELEN]
    mov qword [rbx + S_LINELEN], 0
    cmp qword [rbx + S_NAMELEN], 0
    jne .say
    lea rcx, [r12 - 1]          ; the first line is the name
    test rcx, rcx
    jz .out
    cmp rcx, MAX_NAME
    jbe .name
    mov ecx, MAX_NAME
.name:
    mov [rbx + S_NAMELEN], rcx
    lea rsi, [rbx + S_LINE]
    lea rdi, [rbx + S_NAME]
    rep movsb
    mov edi, K_JOIN
    call post
    jmp .out
.say:
    lea rdi, [r12 + 32]
    call rt_malloc
    mov qword [rax + M_KIND], K_SAY
    mov [rax + M_FROM], rbx
    mov [rax + M_LEN], r12
    lea rsi, [rbx + S_LINE]
    lea rdi, [rax + M_TEXT]
    mov rcx, r12
    push rax
    rep movsb
    pop rsi
    lea rdi, [room_mb]
    call mb_send
.out:
    pop r12
    ret

post:                           ; edi = kind, rbx = session: a message for the room
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

release:                        ; rdi = session: drop one reference; the last one frees it
    dec qword [rdi + S_REFS]
    jnz .ret
    push rdi
    mov eax, 3
    mov rdi, [rdi + S_FD]
    syscall
    pop rdi
    jmp rt_free
.ret:
    ret

; ---- writer: its mailbox -> the socket ------------------------------------------------

writer:                         ; rdi = session
    push rbx
    push r12
    push r13
    mov rbx, rdi
.next:
    lea rdi, [rbx + S_MB]
    call mb_recv
    test rax, rax
    jz .cancelled
    mov r12, rax
    cmp qword [r12 + M_KIND], K_STOP
    je .stop
    xor r13d, r13d              ; bytes written so far
    cmp qword [rbx + S_DEAD], 0
    jne .done
.write:
    mov eax, 1
    mov rdi, [rbx + S_FD]
    lea rsi, [r12 + M_TEXT + r13]
    mov rdx, [r12 + M_LEN]
    sub rdx, r13
    syscall
    cmp rax, -11
    jne .wrote
    mov rdi, [rbx + S_FD]       ; the client isn't keeping up: wait until it reads
    call rt_await_writable
    test rax, rax
    jz .write
    mov rdi, r12
    call rt_free
    jmp .cancelled
.wrote:
    test rax, rax
    js .dead
    add r13, rax
    cmp r13, [r12 + M_LEN]
    jb .write
    jmp .done
.dead:
    mov qword [rbx + S_DEAD], 1 ; the client is gone: drop everything from now on
.done:
    mov rax, [r12 + M_LEN]
    sub [rbx + S_PENDING], rax
    mov rdi, r12
    call rt_free
    jmp .next
.stop:
    mov rdi, r12
    call rt_free
    jmp .out
.cancelled:                     ; kicked: throw away what's queued
    mov rdi, [rbx + S_MB + MB_HEAD]
    test rdi, rdi
    jz .out
    mov rax, [rdi + M_NEXT]
    mov [rbx + S_MB + MB_HEAD], rax
    call rt_free
    jmp .cancelled
.out:
    mov rdi, rbx
    call release
    pop r13
    pop r12
    pop rbx
    ret

; ---- the room ---------------------------------------------------------------------------

room:
    push rbx
    push r12
    push r13
.next:
    lea rdi, [room_mb]
    call mb_recv
    mov rbx, rax
    mov r12, [rbx + M_FROM]
    mov rax, [rbx + M_KIND]
    cmp rax, K_JOIN
    je .join
    cmp rax, K_LEAVE
    je .leave
    lea rsi, [colon]            ; K_SAY: "name: text" to everyone else
    mov rdi, r12
    call compose
    lea rsi, [rbx + M_TEXT]
    mov rcx, [rbx + M_LEN]
    call append
    mov rdi, r12
    call broadcast
    jmp .done
.join:
    call find
    test rax, rax
    jns .done
    mov rax, [nmembers]
    cmp rax, MAX_MEMBERS
    jae .done
    mov [members + rax*8], r12
    inc qword [nmembers]
    lea rsi, [joined]
    call notice
    jmp .done
.leave:
    call find
    test rax, rax
    js .done                    ; never joined, or already kicked
    call remove
    lea rsi, [left]
    call notice
    mov edi, 32                 ; its writer gets K_STOP last: nothing can follow it
    call rt_malloc
    mov qword [rax + M_KIND], K_STOP
    lea rdi, [r12 + S_MB]
    mov rsi, rax
    call mb_send
.done:
    call kicks
    mov rdi, rbx
    call rt_free
    jmp .next

find:                           ; r12 = session -> rax = its index in members, or -1
    xor eax, eax
.loop:
    cmp rax, [nmembers]
    jae .none
    cmp [members + rax*8], r12
    je .ret
    inc rax
    jmp .loop
.none:
    mov rax, -1
.ret:
    ret

remove:                         ; rax = index: the last member fills the hole
    dec qword [nmembers]
    mov rcx, [nmembers]
    mov rdx, [members + rcx*8]
    mov [members + rax*8], rdx
    ret

notice:                         ; r12 = session, rsi = " joined" / " left": "* name ..." to the others
    push rsi
    lea rsi, [star]
    mov rdi, r12
    call compose
    pop rsi
    xor ecx, ecx
.len:
    cmp byte [rsi + rcx], 0
    je .got
    inc ecx
    jmp .len
.got:
    call append
    mov rdi, r12
    jmp broadcast

compose:                        ; rdi = session, rsi = "*" or ":": out = "* name" / "name: "
    push rsi
    lea r8, [out]
    xor edx, edx
    cmp byte [rsi], '*'
    jne .name
    mov word [r8], '* '
    mov edx, 2
.name:
    mov rcx, [rdi + S_NAMELEN]
    lea rsi, [rdi + S_NAME]
    lea rdi, [r8 + rdx]
    add rdx, rcx
    rep movsb
    pop rsi
    cmp byte [rsi], ':'
    jne .done
    mov word [r8 + rdx], ': '
    add rdx, 2
.done:
    mov [out_len], rdx
    ret

append:                         ; rsi, rcx: add to out
    mov rdi, [out_len]
    add [out_len], rcx
    lea rdi, [out + rdi]
    rep movsb
    ret

broadcast:                      ; out to every member except rdi (and those being kicked)
    push rbx
    push r12
    push r13
    mov r12, rdi
    xor ebx, ebx
.each:
    cmp rbx, [nmembers]
    jae .done
    mov r13, [members + rbx*8]
    inc rbx
    cmp r13, r12
    je .each
    cmp qword [r13 + S_KICK], 0
    jne .each
    mov rax, [r13 + S_PENDING]
    add rax, [out_len]
    cmp rax, LIMIT
    jbe .send
    mov qword [r13 + S_KICK], 1 ; too slow: kick it after this message
    jmp .each
.send:
    mov rdi, [out_len]
    add [r13 + S_PENDING], rdi
    add rdi, 32
    call rt_malloc
    mov qword [rax + M_KIND], K_DELIVER
    mov rcx, [out_len]
    mov [rax + M_LEN], rcx
    lea rsi, [out]
    lea rdi, [rax + M_TEXT]
    push rax
    rep movsb
    pop rsi
    lea rdi, [r13 + S_MB]
    call mb_send
    jmp .each
.done:
    pop r13
    pop r12
    pop rbx
    ret

kicks:                          ; remove every member marked S_KICK, and tell the others
    push r12
.scan:
    xor eax, eax
.look:
    cmp rax, [nmembers]
    jae .none
    mov r12, [members + rax*8]
    cmp qword [r12 + S_KICK], 0
    jne .kick
    inc rax
    jmp .look
.kick:
    call remove
    mov rdi, [r12 + S_READER]   ; both of its actors stop at their next await
    call rt_cancel
    mov rdi, [r12 + S_WRITER]
    call rt_cancel
    lea rsi, [left]
    call notice
    jmp .scan
.none:
    pop r12
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
