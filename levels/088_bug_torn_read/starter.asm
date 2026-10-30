; Level 88 — Torn Read
;
; A shared 16-byte record { count, check } that must always satisfy check = 3*count + 1.
; One writer thread publishes 1, 2, 3, ... (always a consistent pair); two reader
; threads keep taking snapshots and count the inconsistent ones. The program prints
; "torn snapshots: 0". Sometimes it doesn't.
;
; 1. Find a schedule with a torn snapshot:   ;! witness schedule = N
; 2. Fix it: every snapshot and every update must be one indivisible 16-byte access.

global _start

UPDATES equ 60
READS   equ 60
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000

section .text
_start:
    lea rdi, [writer]
    xor esi, esi
    call spawn
    lea rdi, [reader]
    mov esi, 1
    call spawn
    lea rdi, [reader]
    mov esi, 2
    call spawn
    xor ebx, ebx
.join:
    cmp ebx, 3
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
    jmp .join
.report:
    mov rax, [torn]
    add al, '0'
    cmp rax, '9'
    jbe .digit
    mov al, '+'                 ; (10 or more)
.digit:
    mov [msg_n], al
    mov eax, 1
    mov edi, 1
    lea rsi, [msg]
    mov edx, MSG_LEN
    syscall
    mov eax, 231
    xor edi, edi
    syscall

spawn:                          ; rdi = function, esi = thread number
    mov r12, rdi                ; (the new thread jumps to r12)
    mov eax, 56
    mov edi, CLONE
    lea rdx, [rsi + 1]
    shl rdx, 12
    lea r8, [stacks + rdx]      ; its stack
    lea rdx, [tids + rsi*4]
    mov r10, rdx
    mov rsi, r8
    xor r8d, r8d
    syscall
    test rax, rax
    jz .child
    ret
.child:
    jmp r12

writer:
    mov ebx, 1
.update:
    lea rcx, [rbx + rbx*2 + 1]  ; check = 3*count + 1
    mov [record], rbx           ; publish the new pair
    mov [record + 8], rcx
    inc ebx
    cmp ebx, UPDATES
    jbe .update
    mov eax, 60
    xor edi, edi
    syscall

reader:
    mov r13d, READS
.snapshot:
    mov rax, [record]           ; take a snapshot
    mov rdx, [record + 8]
    lea rcx, [rax + rax*2 + 1]
    test rax, rax
    jz .fine                    ; (nothing published yet: 0, 0)
    cmp rdx, rcx
    je .fine
    lock inc qword [torn]
.fine:
    dec r13d
    jnz .snapshot
    mov eax, 60
    xor edi, edi
    syscall

section .data
msg:    db "torn snapshots: "
msg_n:  db "?", 10
MSG_LEN equ $ - msg

section .bss
alignb 16
record: resq 2                  ; { count, check }: 16-byte aligned
torn:   resq 1
tids:   resd 4
alignb 16
stacks: resb 4 * 4096
