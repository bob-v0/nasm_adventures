; Level 83 — Memory Ordering (reference)
; x, y, r1, r2 are dwords, all 0 at the start.
global sb_left, sb_right, fenced_left, fenced_right
extern x, y, r1, r2

section .text
sb_left:                        ; x = 1; r1 = y
    mov dword [x], 1
    mov eax, [y]
    mov [r1], eax
    ret

sb_right:                       ; y = 1; r2 = x
    mov dword [y], 1
    mov eax, [x]
    mov [r2], eax
    ret

fenced_left:                    ; the store must be visible before the load
    mov dword [x], 1
    mfence
    mov eax, [y]
    mov [r1], eax
    ret

fenced_right:
    mov dword [y], 1
    mfence
    mov eax, [x]
    mov [r2], eax
    ret

;! witness schedule = 16
