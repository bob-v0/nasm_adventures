; Level 172 — reference fix: state lives in rbx and r12, which syscall preserves
;
; Prints the three log lines from `lines` and exits with the number of
; lines written (3). It prints one line and exits with a strange status.
;
; Fix it by changing only WHICH registers hold the program's state:
; at most 12 changed lines, and no extra instructions.

%include "level172.inc"

global _start

section .text
_start:
    mov ebx, 0                  ; lines written so far
    mov r12, lines              ; r12 walks through the lines

    mov eax, 1                  ; write(1, r12, LINE_LEN)
    mov edi, 1
    mov rsi, r12
    mov edx, LINE_LEN
    syscall
    lea rbx, [rbx + 1]          ; one more line written
    lea r12, [r12 + LINE_LEN]   ; next line

    mov eax, 1
    mov edi, 1
    mov rsi, r12
    mov edx, LINE_LEN
    syscall
    lea rbx, [rbx + 1]
    lea r12, [r12 + LINE_LEN]

    mov eax, 1
    mov edi, 1
    mov rsi, r12
    mov edx, LINE_LEN
    syscall
    lea rbx, [rbx + 1]

    mov edi, ebx                ; exit(lines written)
    mov eax, 60
    syscall
