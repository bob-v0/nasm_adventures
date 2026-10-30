; Level 86 — Logical Race
;
; Two parts of a service, and every memory access in them is atomic:
;  - a rate limiter: at most 10 requests may be admitted. 4 threads try 6 each.
;  - accounts a and b hold 1000 together. 2 threads move money between them; an auditor
;    checks again and again that a + b == 1000.
; It should print "admitted 10, failed audits  0". It rarely does.
;
; 1. Find such a schedule:   ;! witness schedule = N
; 2. Fix it. (spin_lock / spin_unlock below are there if you want them.)

global _start

LIMIT equ 10
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000

section .text
_start:
    xor ebx, ebx
.spawn:                         ; threads 0-3: requests, 4-5: transfers, 6: the auditor
    cmp ebx, 7
    je .join
    mov r12, rbx
    mov eax, 56
    mov edi, CLONE
    lea rsi, [rbx + 1]
    shl rsi, 12
    lea rsi, [stacks + rsi]
    lea rdx, [tids + rbx*4]
    mov r10, rdx
    xor r8d, r8d
    syscall
    test rax, rax
    jz thread
    inc ebx
    jmp .spawn
.join:
    xor ebx, ebx
.next:
    cmp ebx, 7
    je .report
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
    inc ebx
    jmp .next
.report:
    mov rax, [admitted]
    mov rdi, msg_admitted + 9
    call two_digits
    mov rax, [failed]
    mov rdi, msg_admitted + 27
    call two_digits
    mov eax, 1
    mov edi, 1
    lea rsi, [msg_admitted]
    mov edx, MSG_LEN
    syscall
    mov eax, 231
    xor edi, edi
    syscall

two_digits:                     ; rax (0..99) -> 2 characters at rdi (a leading space)
    mov ecx, 10
    xor edx, edx
    div ecx
    add dl, '0'
    mov [rdi + 1], dl
    mov byte [rdi], ' '
    test eax, eax
    jz .done
    add al, '0'
    mov [rdi], al
.done:
    ret

thread:
    cmp r12, 4
    jb requests
    cmp r12, 6
    jb transfers
    jmp auditor

requests:                       ; try to get 6 requests admitted
    mov r13d, 6
.try:
    cmp qword [admitted], LIMIT ; room left?
    jae .refused
    mov ecx, 5                  ; (validate the request...)
.check:
    dec ecx
    jnz .check
    lock inc qword [admitted]   ; admit it
.refused:
    dec r13d
    jnz .try
    jmp exit_thread

transfers:                      ; move 1 back and forth, 20 times
    mov r13d, 20
.move:
    lock sub qword [a], 1       ; take it from a...
    lock add qword [b], 1       ; ...and give it to b
    lock sub qword [b], 1
    lock add qword [a], 1
    dec r13d
    jnz .move
    jmp exit_thread

auditor:
    mov r13d, 30
.audit:
    mov rax, [a]                ; every read is atomic (aligned qwords)
    add rax, [b]
    cmp rax, 1000
    je .ok
    lock inc qword [failed]
.ok:
    dec r13d
    jnz .audit
exit_thread:
    mov eax, 60
    xor edi, edi
    syscall

spin_lock:                      ; rdi = a lock dword (0 = free)
    mov eax, 1
    xchg eax, [rdi]
    test eax, eax
    jz .got
    pause
    jmp spin_lock
.got:
    ret

spin_unlock:                    ; rdi = the lock
    mov dword [rdi], 0
    ret

section .data
msg_admitted: db "admitted ??, failed audits ??", 10
MSG_LEN equ $ - msg_admitted
alignb 8
a: dq 600
b: dq 400

section .bss
alignb 64
admitted: resq 1
failed:   resq 1
bank:     resd 1                ; a lock, if you need one
tids:     resd 8
alignb 16
stacks:   resb 8 * 4096
