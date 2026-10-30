; Level 81 — Weakly-Ordered Stores (reference)
;
; A producer fills a 16-qword buffer for each of 10 rounds and then raises a flag; a
; consumer waits for the flag, checks the buffer's sum, and acknowledges. To be fast,
; the producer writes the buffer with non-temporal stores (movnti), which bypass the
; cache. The program prints "bad rounds: 0"... or, under some schedules, not.
;
; 1. Find such a schedule:   ;! witness schedule = N
; 2. Fix it.

global _start

ROUNDS equ 10
WORDS  equ 16
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000

section .text
_start:
    lea r12, [producer]
    xor esi, esi
    call spawn
    lea r12, [consumer]
    mov esi, 1
    call spawn
    xor ebx, ebx
.join:
    cmp ebx, 2
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
    mov eax, [bad]
    cmp eax, 9
    jbe .digit
    mov eax, 9                  ; (9 or more)
.digit:
    add al, '0'
    mov [msg_n], al
    mov eax, 1
    mov edi, 1
    lea rsi, [msg]
    mov edx, MSG_LEN
    syscall
    mov eax, 231
    xor edi, edi
    syscall

spawn:                          ; r12 = function, esi = number
    mov eax, 56
    mov edi, CLONE
    lea r8, [rsi + 1]
    shl r8, 12
    lea r8, [stacks + r8]
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

producer:
    mov ebx, 1                  ; round
.round:
    xor ecx, ecx                ; buffer[i] = round * 100 + i
.fill:
    imul rax, rbx, 100
    add rax, rcx
    movnti [buffer + rcx*8], rax ; streaming store: straight to memory, bypassing the cache
    inc ecx
    cmp ecx, WORDS
    jb .fill
    sfence                      ; the streaming stores are visible before anything later
    mov [ready], ebx            ; publish: round N's data is there
.wait_ack:
    pause
    cmp [ack], ebx
    jne .wait_ack
    inc ebx
    cmp ebx, ROUNDS
    jbe .round
    mov eax, 60
    xor edi, edi
    syscall

consumer:
    mov ebx, 1
.round:
    pause
    cmp [ready], ebx            ; wait for round N
    jne .round
    xor eax, eax                ; sum the buffer
    xor ecx, ecx
.sum:
    add rax, [buffer + rcx*8]
    inc ecx
    cmp ecx, WORDS
    jb .sum
    imul rdx, rbx, 100 * WORDS  ; expected: 1600 * round + (0 + 1 + ... + 15)
    add rdx, 120
    cmp rax, rdx
    je .good
    inc dword [bad]
.good:
    mov [ack], ebx
    inc ebx
    cmp ebx, ROUNDS
    jbe .round
    mov eax, 60
    xor edi, edi
    syscall

section .data
msg:   db "bad rounds: "
msg_n: db "?", 10
MSG_LEN equ $ - msg

section .bss
alignb 64
buffer: resq WORDS
ready:  resd 16
ack:    resd 16
bad:    resd 1
tids:   resd 2
alignb 16
stacks: resb 3 * 4096
;! witness schedule = 1
