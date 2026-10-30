; Level 133 — Bug: Unchecked Length
;
; set_name(rdi = account, rsi = name): store a NUL-terminated name in the account.
;
; Account layout:  +0  name     16 bytes (a C string: at most 15 characters + NUL)
;                  +16 balance  qword
;
; Customers with long names report that their balance changed when they renamed
; themselves. Prove it with a witness (a name that breaks the original), e.g.
;     ;! witness name = "Ann"
; then fix it: names that don't fit are cut to 15 characters. At most 5 changed lines.

global set_name

section .text
set_name:
.copy:
    mov al, [rsi]
    mov [rdi], al
    test al, al
    jz .done
    inc rsi
    inc rdi
    jmp .copy
.done:
    ret
