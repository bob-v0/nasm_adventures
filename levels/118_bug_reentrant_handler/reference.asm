; Level 118 — reference fix
;
; Prints the numbers 1 to 20, one per line. When SIGUSR1 arrives, it must print
; a line "signal" (once per signal), between two complete lines.
;
; Usually the output is fine. Sometimes a number comes out mangled, or "signal"
; appears in the middle of a line. Make it correct wherever the signal lands,
; changing at most 10 lines.

SA_RESTORER equ 0x04000000

global _start

section .text
_start:
    mov eax, 13                     ; rt_sigaction(SIGUSR1, &act, NULL, 8)
    mov edi, 10
    lea rsi, [act]
    xor edx, edx
    mov r10d, 8
    syscall
    mov r12d, 1
.loop:
    call report_signals             ; fix: print pending signals between lines
    mov rdi, r12
    call print_number
    inc r12
    cmp r12, 20
    jbe .loop
    call report_signals             ; fix
    mov eax, 60
    xor edi, edi
    syscall

on_usr1:                            ; SIGUSR1: only record it (async-signal-safe)
    inc byte [pending]              ; fix: one instruction, can't be torn by another signal
    ret

report_signals:                     ; fix (+7): print one line per recorded signal
    cmp byte [pending], 0
    je .none
    dec byte [pending]
    lea rdi, [msg_signal]
    call print_text
    jmp report_signals
.none:
    ret

restorer:
    mov eax, 15
    syscall

; print_number(rdi): formats rdi into `out` (right-aligned) and writes it
print_number:
    lea rsi, [out + 20]
    mov byte [rsi], 10
    mov rax, rdi
    mov ecx, 10
.digit:
    xor edx, edx
    div rcx
    add dl, '0'
    dec rsi
    mov [rsi], dl
    test rax, rax
    jnz .digit
    mov [out_start], rsi
    lea rdx, [out + 21]
    sub rdx, rsi
    mov [out_len], rdx
    jmp flush

; print_text(rdi): copies the line at rdi (ending with a newline) into `out` and writes it
print_text:
    xor ecx, ecx
.length:
    inc rcx
    cmp byte [rdi + rcx - 1], 10
    jne .length
    mov [out_len], rcx
    lea rsi, [out + 21]
    sub rsi, rcx
    mov [out_start], rsi
.copy:
    mov al, [rdi]
    mov [rsi], al
    inc rdi
    inc rsi
    dec rcx
    jnz .copy

flush:                              ; write [out_len] bytes from [out_start]
    mov rsi, [out_start]
    mov rdx, [out_len]
    mov eax, 1
    mov edi, 1
    syscall
    ret

section .data
act:        dq on_usr1, SA_RESTORER, restorer, 0
msg_signal: db "signal", 10
out:        times 21 db ' '
out_start:  dq 0
out_len:    dq 0
pending:    db 0                   ; fix
