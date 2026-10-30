; Level 104 harness (the same as level 106) (the game's): producers and consumers around your channel.
;   argv: P C N CAP  -> P producers each send N values (p*1000 + i) through a channel of
;   capacity CAP to C consumers. Every send and receive is logged for the grader.
global _start, ring_log, ring_log_len
extern chan_init, chan_send, chan_recv, chan_close
extern rt_spawn, rt_run, rt_yield

section .text
_start:
    mov rsi, [rsp + 16]
    call atoi
    mov [P], rax
    mov rsi, [rsp + 24]
    call atoi
    mov [C], rax
    mov rsi, [rsp + 32]
    call atoi
    mov [N], rax
    mov rsi, [rsp + 40]
    call atoi
    lea rdi, [chan]
    mov rsi, rax
    call chan_init
    xor ebx, ebx
.producers:
    cmp rbx, [P]
    jae .consumers_
    lea rdi, [producer]
    mov rsi, rbx
    call rt_spawn
    inc rbx
    jmp .producers
.consumers_:
    xor ebx, ebx
.consumers:
    cmp rbx, [C]
    jae .run
    lea rdi, [consumer]
    mov rsi, rbx
    call rt_spawn
    inc rbx
    jmp .consumers
.run:
    call rt_run
    mov rdi, rax                ; exit status = tasks stuck forever
    mov eax, 60
    syscall

producer:                       ; rdi = p
    push rbx
    push r12
    sub rsp, 8
    imul rbx, rdi, 1000
    xor r12d, r12d
.next:
    cmp r12, [N]
    jae .done
    lea rdi, [chan]
    lea rsi, [rbx + r12]
    call chan_send
    mov edi, 1
    lea rsi, [rbx + r12]
    call log
    call rt_yield
    inc r12
    jmp .next
.done:
    inc qword [finished]
    mov rax, [finished]
    cmp rax, [P]
    jne .out
    lea rdi, [chan]             ; the last producer closes the channel
    call chan_close
.out:
    add rsp, 8
    pop r12
    pop rbx
    ret

consumer:
    sub rsp, 8
.next:
    lea rdi, [chan]
    call chan_recv
    test rdx, rdx
    jz .done
    mov edi, 2
    mov rsi, rax
    call log
    call rt_yield
    jmp .next
.done:
    add rsp, 8
    ret

log:                            ; edi = 1 (sent) / 2 (received), rsi = value
    mov rax, [ring_log_len]
    cmp rax, 4096
    jae .full
    shl rax, 4
    lea rcx, [ring_log]
    mov [rcx + rax], rdi
    mov [rcx + rax + 8], rsi
    inc qword [ring_log_len]
.full:
    ret

atoi:
    xor eax, eax
.digit:
    movzx ecx, byte [rsi]
    sub ecx, '0'
    cmp ecx, 9
    ja .done
    imul rax, rax, 10
    add rax, rcx
    inc rsi
    jmp .digit
.done:
    ret

section .bss
P: resq 1
C: resq 1
N: resq 1
finished: resq 1
ring_log_len: resq 1
ring_log: resq 2 * 4096
alignb 64
chan: resb 4096                 ; your struct channel lives here, zeroed
