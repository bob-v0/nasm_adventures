; Level 80's harness (the game's): argv = P C N CAP. P producer threads each put N
; values (p*1000 + i) into your queue (capacity CAP); C consumer threads get until the
; queue is closed (the last producer closes it). Every put and get is logged.
; Also here: mutex_lock / mutex_unlock (level 87's futex mutex), for you to use.
global _start, ring_log, ring_log_len, mutex_lock, mutex_unlock
extern queue_init, queue_put, queue_get, queue_close

CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000
FUTEX_WAIT equ 0
FUTEX_WAKE equ 1

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
    lea rdi, [queue]
    mov rsi, rax
    call queue_init
    xor ebx, ebx
.spawn:
    mov rax, [P]
    add rax, [C]
    cmp rbx, rax
    jae .join
    mov r12, rbx                ; thread number: producers first, then consumers
    mov eax, 56
    mov edi, CLONE
    lea rsi, [rbx + 1]
    shl rsi, 13
    lea rsi, [stacks + rsi]
    lea rdx, [tids + rbx*4]
    mov r10, rdx
    xor r8d, r8d
    syscall
    test rax, rax
    jz thread
    inc rbx
    jmp .spawn
.join:
    xor ebx, ebx
.next:
    mov rax, [P]
    add rax, [C]
    cmp rbx, rax
    jae .done
.wait:
    mov edx, [tids + rbx*4]
    test edx, edx
    jz .joined
    mov eax, 202
    lea rdi, [tids + rbx*4]
    xor esi, esi
    xor r10d, r10d
    syscall
    jmp .wait
.joined:
    inc rbx
    jmp .next
.done:
    mov eax, 231
    xor edi, edi
    syscall

thread:
    cmp r12, [P]
    jae consumer
producer:                       ; r12 = p
    imul r13, r12, 1000
    xor r14d, r14d
.put:
    cmp r14, [N]
    jae .finished
    lea rdi, [queue]
    lea rsi, [r13 + r14]
    call queue_put
    mov edi, 1
    lea rsi, [r13 + r14]
    call log
    inc r14
    jmp .put
.finished:
    mov eax, 1
    lock xadd [finished], rax
    inc rax
    cmp rax, [P]
    jne exit_thread
    lea rdi, [queue]            ; the last producer closes the queue
    call queue_close
    jmp exit_thread

consumer:
.get:
    lea rdi, [queue]
    call queue_get
    test rdx, rdx
    jz exit_thread
    mov edi, 2
    mov rsi, rax
    call log
    jmp .get
exit_thread:
    mov eax, 60
    xor edi, edi
    syscall

log:                            ; edi = 1 put / 2 got, rsi = value
    mov eax, 1
    lock xadd [ring_log_len], rax
    cmp rax, 4096
    jae .full
    shl rax, 4
    lea rcx, [ring_log]
    mov [rcx + rax], rdi
    mov [rcx + rax + 8], rsi
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

mutex_lock:                     ; rdi = the lock
    xor eax, eax
    mov edx, 1
    lock cmpxchg [rdi], edx     ; 0 -> 1: got it, nobody waiting
    jz .got
    mov edx, 2
    cmp eax, 2
    je .sleep
.mark:
    mov eax, 2
    xchg eax, [rdi]             ; say "someone waits"; if it was free meanwhile, we own it
    test eax, eax
    jz .got
.sleep:
    push rdi
    mov eax, 202                ; futex(m, FUTEX_WAIT, 2, 0): sleep if it's still 2
    mov esi, FUTEX_WAIT
    mov edx, 2
    xor r10d, r10d
    syscall
    pop rdi
    jmp .mark
.got:
    ret

mutex_unlock:                   ; rdi = the lock
    mov eax, -1
    lock xadd [rdi], eax        ; 1 -> 0: nobody waited, done
    cmp eax, 1
    je .done
    mov dword [rdi], 0          ; it was 2: free it and wake one sleeper
    mov eax, 202
    mov esi, FUTEX_WAKE
    mov edx, 1
    syscall
.done:
    ret

section .bss
P: resq 1
C: resq 1
N: resq 1
alignb 64
finished: resq 8
ring_log_len: resq 8
ring_log: resq 2 * 4096
tids: resd 16
alignb 64
queue: resb 4096                ; your queue lives here, zeroed
alignb 16
stacks: resb 17 * 8192
