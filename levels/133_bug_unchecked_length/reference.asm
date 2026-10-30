; Level 133 — reference fix
;
; Any name of 16 characters or more runs into the balance: at 16 the terminating
; NUL lands on it, longer names overwrite it with text.
;! witness name = "Maximilian Alexander von Habsburg"

global set_name

section .text
set_name:
    lea rdx, [rdi + 15]         ; fix: the last byte of the field is for the NUL
.copy:
    cmp rdi, rdx                ; fix: field full?
    je .terminate               ; fix
    mov al, [rsi]
    mov [rdi], al
    test al, al
    jz .done
    inc rsi
    inc rdi
    jmp .copy
.terminate:
    mov byte [rdi], 0           ; fix: cut the name short
.done:
    ret
