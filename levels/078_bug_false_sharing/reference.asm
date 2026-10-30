; Level 78 — False Sharing (reference)
;
; Four threads count events, each in its OWN counter: no sharing, no locks needed, and
; it should scale perfectly. On the game's 4-core CPU it takes about as long as doing all
; the work on one core, several times what it should.
;
; Find out why, and fix it. (The counters must still be correct.)

global _start, counters

THREADS equ 4
EVENTS  equ 300
STRIDE  equ 64                  ; one cache line per counter: no two cores share a line
CLONE equ 0x100 | 0x200 | 0x400 | 0x800 | 0x10000 | 0x40000 | 0x100000 | 0x200000

section .text
_start:
    xor ebx, ebx
.spawn:
    cmp ebx, THREADS
    je .join
    imul r12, rbx, STRIDE       ; this thread's counter
    lea r12, [counters + r12]
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
    jz worker
    inc ebx
    jmp .spawn
.join:
    xor ebx, ebx
.next:
    cmp ebx, THREADS
    je .done
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
.done:
    xor eax, eax                ; the total, 4 digits
    xor ebx, ebx
.sum:
    imul rcx, rbx, STRIDE
    add rax, [counters + rcx]
    inc ebx
    cmp ebx, THREADS
    jb .sum
    lea rdi, [msg_n + 3]
    mov ecx, 10
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    mov [rdi], dl
    dec rdi
    cmp rdi, msg_n
    jae .digit
    mov eax, 1
    mov edi, 1
    lea rsi, [msg]
    mov edx, MSG_LEN
    syscall
    mov eax, 231
    xor edi, edi
    syscall

worker:                         ; r12 = my counter
    mov ecx, EVENTS
.event:
    inc qword [r12]             ; count it (only this thread touches this counter)
    dec ecx
    jnz .event
    mov eax, 60
    xor edi, edi
    syscall

section .data
msg:   db "events "
msg_n: db "????", 10
MSG_LEN equ $ - msg

section .bss
alignb 64
counters: resb THREADS * STRIDE ; one per thread
tids:     resd THREADS
alignb 16
stacks:   resb (THREADS + 1) * 4096
