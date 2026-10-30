; Level 108 — Timers
;
; Level 109's echo server. Add idle timeouts: a client that has sent nothing for 5
; seconds (since it connected, or since its last data) gets "timeout\n" and is
; disconnected. Be accurate: not before 5 s, and within 5.2 s.
; Use a timerfd in the same epoll set, and clock_gettime(CLOCK_MONOTONIC).
global _start
section .text
_start:
    mov eax, 41                 ; socket(AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0)
    mov edi, 2
    mov esi, 1 | 0o4000
    xor edx, edx
    syscall
    mov r12, rax
    mov eax, 54                 ; setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, 4)
    mov rdi, r12
    mov esi, 1
    mov edx, 2
    lea r10, [one]
    mov r8d, 4
    syscall
    mov eax, 49                 ; bind(fd, &addr, 16)
    mov rdi, r12
    lea rsi, [addr]
    mov edx, 16
    syscall
    test rax, rax
    js fail
    mov eax, 50                 ; listen(fd, 16)
    mov rdi, r12
    mov esi, 16
    syscall
    mov eax, 291                ; epoll_create1(0)
    xor edi, edi
    syscall
    mov r13, rax
    mov rsi, r12
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
    mov rbx, [events + rax + 4]   ; data = the fd (struct epoll_event is packed: 12 bytes)
    inc r15
    cmp rbx, r12
    jne .client
    mov eax, 288                ; accept4(listener, 0, 0, SOCK_NONBLOCK)
    mov rdi, r12
    xor esi, esi
    xor edx, edx
    mov r10d, 0o4000
    syscall
    test rax, rax
    js .event
    mov rsi, rax
    call watch
    jmp .event
.client:
    xor eax, eax                ; read(fd, buf, 4096)
    mov rdi, rbx
    lea rsi, [buf]
    mov edx, 4096
    syscall
    cmp rax, -11                ; EAGAIN: nothing after all
    je .event
    test rax, rax
    jle .close
    mov rdx, rax                ; write it back (small: it fits)
    mov eax, 1
    mov rdi, rbx
    lea rsi, [buf]
    syscall
    jmp .event
.close:
    mov eax, 3
    mov rdi, rbx
    syscall
    jmp .event

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
fail:
    mov eax, 60
    mov edi, 1
    syscall

section .data
one:  dd 1
addr: dw 2                      ; AF_INET
      db 7000 >> 8, 7000 & 0xFF ; the port, big-endian
      db 127, 0, 0, 1
      times 8 db 0
section .bss
ev:     resb 12
events: resb 12 * 16
buf:    resb 4096
