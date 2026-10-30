; Level 83's harness (the game's): argv[1] is "plain" or "fenced". Two threads run
; the left and the right side of the test at the same time; then it prints r1 and r2.
global _start, x, y, r1, r2
extern sb_left, sb_right, fenced_left, fenced_right

CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000

section .text
_start:
    mov rax, [rsp + 16]         ; argv[1]
    lea r12, [sb_left]
    lea r13, [sb_right]
    cmp byte [rax], 'f'
    jne .go
    lea r12, [fenced_left]
    lea r13, [fenced_right]
.go:
    mov rdi, r12
    xor esi, esi
    call spawn
    mov rdi, r13
    mov esi, 1
    call spawn
    mov eax, 1
    xchg eax, [go]              ; ready, set... go (both start at about the same time)
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
    mov eax, [r1]
    add al, '0'
    mov [msg + 3], al
    mov eax, [r2]
    add al, '0'
    mov [msg + 8], al
    mov eax, 1
    mov edi, 1
    lea rsi, [msg]
    mov edx, MSG_LEN
    syscall
    mov eax, 231
    xor edi, edi
    syscall

spawn:                          ; rdi = function, esi = number
    mov r14, rdi
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
    pause
    cmp dword [go], 0           ; wait for the start
    je .child
    call r14
    mov eax, 60
    xor edi, edi
    syscall

section .data
msg: db "r1=? r2=?", 10
MSG_LEN equ $ - msg

section .bss
alignb 64
x:  resd 16                     ; each on its own cache line
y:  resd 16
r1: resd 16
r2: resd 16
go: resd 16
tids: resd 2
alignb 16
stacks: resb 3 * 4096
