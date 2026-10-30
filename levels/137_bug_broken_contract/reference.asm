; Level 137 — reference fix
;
; frame(rdi = buf, rsi = len): prepend a length byte to a packet in place and
; return its checksum.
;   1. shift buf[0 .. len) up by one byte (an overlapping move, done backwards)
;   2. buf[0] = len
;   3. return the sum of ring_mix(b) over the len + 1 bytes of the framed packet
;
; It passes its own tests. Inside the real application it corrupts the
; application's variables, and some calls to ring_mix see a misaligned stack.
; Fix it, changing at most 3 lines.

extern ring_mix
global frame

section .text
frame:
    push rbx                    ; fix: rbx is callee-saved, and a third push re-aligns the stack
    push r12
    push r13
    mov r12, rdi                ; buf
    mov r13, rsi                ; len

    std                         ; overlapping move to higher addresses: go backwards
    lea rsi, [rdi + rsi - 1]    ; last source byte
    lea rdi, [rsi + 1]          ; last destination byte
    mov rcx, r13
    rep movsb
    cld                         ; fix: DF must be clear again
    mov [r12], r13b             ; length byte

    xor ebx, ebx                ; checksum
    lea r13, [r13 + 1]          ; bytes to mix
.mix:
    movzx edi, byte [r12]
    call ring_mix
    add rbx, rax
    inc r12
    dec r13
    jnz .mix

    mov rax, rbx
    pop r13
    pop r12
    pop rbx                     ; fix
    ret
