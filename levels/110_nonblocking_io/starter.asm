; Level 110 — Non-blocking I/O
;
; fd 3 and fd 4 are pipes from two sensors, A and B. Each sends lines (ending in a
; newline) at its own pace, sometimes in pieces. Print each line as soon as it is
; complete, as "A: line" or "B: line", in the order the lines complete. When both
; pipes are closed, print "done" and exit 0.
;
; This version reads with ordinary (blocking) reads, A then B, one line each. While it
; waits for A, B's lines pile up unseen. Make both descriptors non-blocking and poll
; them instead (sleeping 1 ms when neither has anything).

global _start

FD     equ 0                    ; struct source
LETTER equ 8
EOF_   equ 16
LEN    equ 24
BUF    equ 32
CAP    equ 512

section .text
_start:
.round:
    lea rbx, [src_a]
    call read_line
    lea rbx, [src_b]
    call read_line
    mov rax, [src_a + EOF_]
    and rax, [src_b + EOF_]
    jz .round
    mov eax, 1
    mov edi, 1
    lea rsi, [done_msg]
    mov edx, 5
    syscall
    mov eax, 60
    xor edi, edi
    syscall

read_line:                      ; rbx = source: read one byte at a time up to a newline
    cmp qword [rbx + EOF_], 0
    jne .ret
.byte:
    xor eax, eax
    mov rdi, [rbx + FD]
    mov rdx, [rbx + LEN]
    lea rsi, [rbx + BUF + rdx]
    mov edx, 1
    syscall
    test rax, rax
    jle .eof
    mov rdx, [rbx + LEN]
    inc qword [rbx + LEN]
    cmp byte [rbx + BUF + rdx], 10
    jne .byte
    mov rax, [rbx + LETTER]
    mov [prefix], al
    mov eax, 1
    mov edi, 1
    lea rsi, [prefix]
    mov edx, 3
    syscall
    mov eax, 1
    mov edi, 1
    lea rsi, [rbx + BUF]
    mov rdx, [rbx + LEN]
    syscall
    mov qword [rbx + LEN], 0
.ret:
    ret
.eof:
    mov qword [rbx + EOF_], 1
    ret

section .data
src_a:  dq 3, 'A', 0, 0
        times CAP db 0
src_b:  dq 4, 'B', 0, 0
        times CAP db 0
prefix: db "?: "
done_msg: db "done", 10
