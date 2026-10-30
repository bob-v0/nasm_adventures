; Level 172 — Bug: Clobbered by the Kernel
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
    mov ecx, 0                  ; lines written so far
    mov r11, lines              ; r11 walks through the lines

    mov eax, 1                  ; write(1, r11, LINE_LEN)
    mov edi, 1
    mov rsi, r11
    mov edx, LINE_LEN
    syscall
    lea rcx, [rcx + 1]          ; one more line written
    lea r11, [r11 + LINE_LEN]   ; next line

    mov eax, 1
    mov edi, 1
    mov rsi, r11
    mov edx, LINE_LEN
    syscall
    lea rcx, [rcx + 1]
    lea r11, [r11 + LINE_LEN]

    mov eax, 1
    mov edi, 1
    mov rsi, r11
    mov edx, LINE_LEN
    syscall
    lea rcx, [rcx + 1]

    mov edi, ecx                ; exit(lines written)
    mov eax, 60
    syscall
