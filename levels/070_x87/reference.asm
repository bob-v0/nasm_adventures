; Level 70 — x87 (Museum) (reference)

global ring_rotate

section .text
ring_rotate:                    ; xmm0 = x, xmm1 = y, xmm2 = angle
    movsd [rsp-8], xmm0
    movsd [rsp-16], xmm1
    movsd [rsp-24], xmm2
    fld qword [rsp-24]          ; st0 = a
    fsincos                     ; st0 = cos, st1 = sin
    fld qword [rsp-8]           ; x, cos, sin
    fmul st0, st1               ; x·cos, cos, sin
    fld qword [rsp-16]          ; y, x·cos, cos, sin
    fmul st0, st3               ; y·sin, x·cos, cos, sin
    fsubp st1, st0              ; x' = x·cos − y·sin, cos, sin
    fstp qword [rsp-32]         ; cos, sin
    fmul qword [rsp-16]         ; y·cos, sin
    fxch st1                    ; sin, y·cos
    fmul qword [rsp-8]          ; x·sin, y·cos
    faddp st1, st0              ; y'
    fstp qword [rsp-40]         ; (empty)
    fld qword [rsp-32]
    fmul st0, st0               ; x'²
    fld qword [rsp-40]
    fmul st0, st0               ; y'², x'²
    faddp st1, st0
    fsqrt                       ; the length
    fnstcw [rsp-48]             ; the control word, as it was
    mov ax, [rsp-48]
    and ax, 0xF3FF
    or ax, 0x0400               ; rounding control (bits 10-11) = 01: down
    mov [rsp-46], ax
    fldcw [rsp-46]
    fistp qword [rsp-56]        ; rounded down, and the stack is empty again
    fldcw [rsp-48]              ; restore
    mov rax, [rsp-56]
    movsd xmm0, [rsp-32]
    movsd xmm1, [rsp-40]
    ret
