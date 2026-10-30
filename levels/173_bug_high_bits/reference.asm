; Level 173 — reference fix
;
; This program prints a user record:
;     user: <name>
;     <badge_w '#' characters>
; and exits with the low byte of the record id.
;
; It worked when it was written. It doesn't now. Find out why and fix it,
; changing at most 2 lines.

%include "level173.inc"

global _start

section .text
_start:
    mov rax, [rec_id]           ; keep the record id for the exit status
    mov r12, rax

    mov eax, 1                  ; write(1, label, LABEL_LEN)
    mov edi, 1
    mov rsi, label
    mov edx, LABEL_LEN
    syscall

    mov rax, r12
    movzx eax, byte [name_len]  ; length of the name (zero-extended: the fix)
    mov rdx, rax
    mov eax, 1                  ; write(1, name, name_len)
    mov edi, 1
    mov rsi, name
    syscall

    mov eax, 1                  ; write(1, newline, 1)
    mov edi, 1
    mov rsi, newline
    mov edx, 1
    syscall

    mov r8, hashes              ; the badge is cut from a row of '#'
    mov rsi, r8
    movzx r8d, word [badge_w]   ; badge width (zero-extended: the fix)
    mov rdx, r8
    mov eax, 1                  ; write(1, hashes, badge_w)
    mov edi, 1
    syscall

    mov eax, 1                  ; write(1, newline, 1)
    mov edi, 1
    mov rsi, newline
    mov edx, 1
    syscall

    mov rdi, r12                ; exit(low byte of the record id)
    mov eax, 60
    syscall

section .data
label:      db "user: "
LABEL_LEN   equ $ - label
newline:    db 10
hashes:     times 64 db '#'
