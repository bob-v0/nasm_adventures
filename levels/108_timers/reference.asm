; Level 108 — Timers (reference)
global _start

IDLE_NS equ 5_000_000_000       ; 5 s without a byte from a client: disconnect it
MAX_FD  equ 1024

section .text
_start:
    mov eax, 41                 ; socket(AF_INET, SOCK_STREAM, 0)
    mov edi, 2
    mov esi, 1
    xor edx, edx
    syscall
    mov r12, rax
    mov eax, 49                 ; bind, listen
    mov rdi, r12
    lea rsi, [addr]
    mov edx, 16
    syscall
    mov eax, 50
    mov rdi, r12
    mov esi, 16
    syscall
    mov eax, 291                ; epoll_create1(0)
    xor edi, edi
    syscall
    mov r13, rax
    mov rsi, r12
    call watch
    mov eax, 283                ; timerfd_create(CLOCK_MONOTONIC, 0)
    mov edi, 1
    xor esi, esi
    syscall
    mov [tfd], rax
    mov eax, 286                ; timerfd_settime(tfd, 0, every 100 ms)
    mov rdi, [tfd]
    xor esi, esi
    lea rdx, [tick]
    xor r10d, r10d
    syscall
    mov rsi, [tfd]
    call watch
loop:
    mov eax, 232                ; epoll_wait(ep, events, 16, -1)
    mov rdi, r13
    lea rsi, [events]
    mov edx, 16
    mov r10, -1
    syscall
    mov r14, rax
    xor r15d, r15d
.event:
    cmp r15, r14
    jae loop
    imul rax, r15, 12
    mov rbx, [events + rax + 4]
    inc r15
    cmp rbx, r12
    je .accept
    cmp rbx, [tfd]
    je .tick
    xor eax, eax                ; a client: read(fd, buf, 4096)
    mov rdi, rbx
    lea rsi, [buf]
    mov edx, 4096
    syscall
    test rax, rax
    jle .gone
    mov rdx, rax                ; echo it
    mov eax, 1
    mov rdi, rbx
    lea rsi, [buf]
    syscall
    call now
    mov [last + rbx*8], rax     ; it's alive
    jmp .event
.gone:
    mov rdi, rbx
    call hang_up
    jmp .event
.accept:
    mov eax, 288                ; accept4(listener, 0, 0, 0)
    mov rdi, r12
    xor esi, esi
    xor edx, edx
    xor r10d, r10d
    syscall
    test rax, rax
    js .event
    cmp rax, MAX_FD
    jae .event
    mov rbx, rax
    mov rsi, rax
    call watch
    call now
    mov [last + rbx*8], rax
    cmp rbx, [max_fd]
    jbe .event
    mov [max_fd], rbx
    jmp .event
.tick:
    xor eax, eax                ; read(tfd, &count, 8): acknowledge the tick
    mov rdi, [tfd]
    lea rsi, [count]
    mov edx, 8
    syscall
    call now
    mov rbp, rax
    xor ebx, ebx
.scan:                          ; every connection quiet for 5 s: say so and hang up
    cmp rbx, [max_fd]
    ja .event
    mov rax, [last + rbx*8]
    test rax, rax
    jz .next
    mov rcx, rbp
    sub rcx, rax
    mov rax, IDLE_NS            ; (too big for an immediate operand)
    cmp rcx, rax
    jb .next
    mov eax, 1
    mov rdi, rbx
    lea rsi, [bye]
    mov edx, BYE_LEN
    syscall
    mov rdi, rbx
    call hang_up
.next:
    inc rbx
    jmp .scan

hang_up:                        ; rdi = fd
    mov qword [last + rdi*8], 0
    mov eax, 3
    syscall
    ret

now:                            ; rax = CLOCK_MONOTONIC in ns
    mov eax, 228
    mov edi, 1
    lea rsi, [ts]
    syscall
    imul rax, [ts], 1_000_000_000
    add rax, [ts + 8]
    ret

watch:                          ; epoll_ctl(ep, ADD, rsi, {EPOLLIN, rsi})
    mov dword [ev], 1
    mov [ev + 4], rsi
    mov eax, 233
    mov rdi, r13
    mov rdx, rsi
    mov esi, 1
    lea r10, [ev]
    syscall
    ret

section .data
addr: dw 2
      db 7000 >> 8, 7000 & 0xFF
      db 127, 0, 0, 1
      times 8 db 0
tick: dq 0, 100_000_000, 0, 100_000_000     ; itimerspec: every 100 ms, first in 100 ms
bye:  db "timeout", 10
BYE_LEN equ $ - bye

section .bss
tfd:    resq 1
max_fd: resq 1
count:  resq 1
ts:     resq 2
ev:     resb 12
events: resb 12 * 16
last:   resq MAX_FD             ; last activity per fd, 0 = not a client
buf:    resb 4096
