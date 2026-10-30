; Level 89 — Data Race (reference)
;
; A server's statistics: 4 worker threads each handle 40 requests, counting every
; request and the bytes it sent in two shared counters. At the end the main thread
; prints the totals. It should say "hits 160 bytes 25600". Sometimes it says less.
;
; 1. Find a schedule that loses updates:   ;! witness schedule = N
; 2. Fix it.

global _start

THREADS  equ 4
REQUESTS equ 40
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000

section .text
_start:
    xor ebx, ebx
.spawn:
    cmp ebx, THREADS
    je .join
    mov eax, 56                 ; clone a worker
    mov edi, CLONE
    lea rsi, [rbx + 1]
    shl rsi, 12
    lea rsi, [stacks + rsi]
    lea rdx, [tids + rbx*4]
    mov r10, rdx
    xor r8d, r8d
    syscall
    test rax, rax
    jz worker
    inc ebx
    jmp .spawn
.join:
    xor ebx, ebx
.next:
    cmp ebx, THREADS
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
    lea rsi, [hits_msg]
    call print
    mov rax, [hits]
    call print_number
    lea rsi, [bytes_msg]
    call print
    mov rax, [bytes]
    call print_number
    lea rsi, [newline]
    call print
    mov eax, 231
    xor edi, edi
    syscall

worker:
    mov r12d, REQUESTS
.request:
    mov eax, 160                ; "handle" a request: it sends 160 bytes
    lock inc qword [hits]       ; count it: read, add and write as one step
    lock add [bytes], rax
    dec r12d
    jnz .request
    mov eax, 60
    xor edi, edi
    syscall

print:                          ; rsi = C string
    xor edx, edx
.len:
    cmp byte [rsi + rdx], 0
    je .write
    inc rdx
    jmp .len
.write:
    mov eax, 1
    mov edi, 1
    syscall
    ret

print_number:                   ; rax = n
    lea rsi, [digits + 23]
    mov byte [rsi], 0
    mov ecx, 10
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test rax, rax
    jnz .digit
    jmp print

section .data
hits_msg:  db "hits ", 0
bytes_msg: db " bytes ", 0
newline:   db 10, 0

section .bss
alignb 64
hits:   resq 1
bytes:  resq 1
tids:   resd THREADS
digits: resb 24
alignb 16
stacks: resb (THREADS + 1) * 4096
;! witness schedule = 1
