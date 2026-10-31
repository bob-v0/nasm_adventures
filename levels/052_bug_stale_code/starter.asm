; Level 52 — Stale Code
;
; A tiny tiered JIT. The worker thread calls hot(x) = 3x + 1 300 times through a
; trampoline, `jmp rel32`, in code memory, and adds up the results. Meanwhile the
; compiler thread produces better versions and installs each one by patching the
; trampoline's rel32: version 2 into buffer 1, then version 3 into buffer 0, where
; version 1 used to be. The program must print "sum 134850".
;
; Sometimes it prints something else, or crashes inside code memory.
;
; 1. Find a schedule that breaks it:   ;! witness schedule = N
; 2. Fix it. (Two things are wrong.)

global _start

N     equ 300
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000
TRAMP equ 3                     ; offsets in code memory: the trampoline,
BUF0  equ 0x1040                ; version buffer 0,
BUF1  equ 0x20C0                ; version buffer 1

section .rodata
v1:     mov eax, edi            ; hot(x) = 3x + 1, three ways
        shl eax, 1
        add eax, edi
        add eax, 1
        ret
v1_end:
v2:     imul eax, edi, 3
        inc eax
        ret
v2_end:
v3:     lea eax, [rdi + rdi*2 + 1]
        ret
v3_end:

section .text
_start:
    mov eax, 9                  ; code memory: 3 pages, read + write + execute
    xor edi, edi
    mov esi, 3 * 4096
    mov edx, 7
    mov r10d, 0x22
    mov r8, -1
    xor r9d, r9d
    syscall
    mov r15, rax
    lea rsi, [v1]               ; version 1 in buffer 0
    lea rdi, [r15 + BUF0]
    mov ecx, v1_end - v1
    rep movsb
    mov byte [r15 + TRAMP], 0xE9            ; the trampoline: jmp buffer 0
    mov dword [r15 + TRAMP + 1], BUF0 - (TRAMP + 5)
    lea rsi, [stacks + 4096]
    lea rdx, [tids]
    lea rcx, [worker]
    call spawn
    lea rsi, [stacks + 8192]
    lea rdx, [tids + 4]
    lea rcx, [compiler]
    call spawn
    lea rdi, [tids]
    call join
    lea rdi, [tids + 4]
    call join
    lea rsi, [sum_msg]
    call print
    mov rax, [sum]
    call print_number
    lea rsi, [newline]
    call print
    mov eax, 231
    xor edi, edi
    syscall

worker:
    xor r12d, r12d              ; x
    xor r13d, r13d              ; the sum
.call:
    mov edi, r12d
    lea rax, [r15 + TRAMP]
    call rax                    ; hot(x), whichever version is installed
    add r13, rax
    inc qword [epoch]           ; a safepoint: no call in progress here
    inc r12d
    cmp r12d, N
    jb .call
    mov [sum], r13
    mov byte [done], 1
    mov eax, 60
    xor edi, edi
    syscall

compiler:
    lea rsi, [v2]               ; version 2 into buffer 1, and install it
    lea rdi, [r15 + BUF1]
    mov ecx, v2_end - v2
    rep movsb
    mov eax, BUF1
    call install
    lea rsi, [v3]               ; version 3 into buffer 0, and install it
    lea rdi, [r15 + BUF0]
    mov ecx, v3_end - v3
    rep movsb
    mov eax, BUF0
    call install
    mov eax, 60
    xor edi, edi
    syscall

install:                        ; eax = the buffer's offset: point the trampoline at it
    sub eax, TRAMP + 5          ; rel32, from the end of the jmp
    mov [r15 + TRAMP + 1], al   ; patch the 4 bytes
    shr eax, 8
    mov [r15 + TRAMP + 2], al
    shr eax, 8
    mov [r15 + TRAMP + 3], al
    shr eax, 8
    mov [r15 + TRAMP + 4], al
    ret

spawn:                          ; rsi = stack top, rdx = &tid, rcx = where the thread starts
    mov r12, rcx
    mov eax, 56
    mov edi, CLONE
    mov r10, rdx
    xor r8d, r8d
    syscall
    test rax, rax
    jnz .parent
    jmp r12                     ; the new thread
.parent:
    ret

join:                           ; rdi = &tid
    mov edx, [rdi]
    test edx, edx
    jz .done
    mov eax, 202                ; futex wait while tid is unchanged
    xor esi, esi
    xor r10d, r10d
    syscall
    jmp join
.done:
    ret

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
sum_msg: db "sum ", 0
newline: db 10, 0

section .bss
alignb 64
epoch:  resq 1
sum:    resq 1
done:   resb 1
alignb 4
tids:   resd 2
digits: resb 24
alignb 16
stacks: resb 3 * 4096
