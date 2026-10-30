; Level 163 — Bug: Signed or Unsigned?
;
; This routine was written for unsigned numbers, then the spec changed to signed.
; Someone updated the comments but not all of the code.
;
; On entry: rdi = a, rsi = b (signed, b != 0), and delta (a signed byte, in .data)
;   rax = max(a, b)       as signed numbers
;   rbx = a / b           signed, rounded toward zero
;   rcx = a + delta       delta is a signed byte (-128 .. 127)
;
; Fix it, changing at most 4 lines.

    mov rax, rdi
    cmp rdi, rsi
    ja .have_max            ; a is the larger one
    mov rax, rsi
.have_max:
    mov r8, rax             ; keep max(a, b)

    mov rax, rdi
    mov edx, 0              ; rdx:rax = a
    div rsi                 ; a / b
    mov rbx, rax

    movzx rcx, byte [delta] ; the signed byte
    add rcx, rdi

    mov rax, r8
