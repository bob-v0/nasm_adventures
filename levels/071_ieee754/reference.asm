; Level 71 — IEEE 754 (reference)

global ring_dtoi

section .text
ring_dtoi:                      ; rdi = the bits
    mov rax, rdi
    shr rax, 52
    and eax, 0x7FF              ; the exponent field
    sub eax, 1023               ; unbiased: value = 1.f × 2^eax
    js .zero                    ; |value| < 1 (zeros and denormals too)
    cmp eax, 63
    jge .indefinite             ; too big for int64 (and inf, NaN: eax = 1024)
    mov rdx, 0x000FFFFFFFFFFFFF
    and rdx, rdi
    bts rdx, 52                 ; the implicit leading 1: m = 1.f × 2^52
    mov ecx, 52
    sub ecx, eax                ; value = m × 2^(eax - 52)
    jl .left
    shr rdx, cl                 ; drop the fraction bits below the point
    jmp .sign
.left:
    neg ecx
    shl rdx, cl
.sign:
    mov rax, rdx
    test rdi, rdi
    jns .done
    neg rax
.done:
    ret
.zero:
    xor eax, eax
    ret
.indefinite:
    mov rax, 0x8000000000000000
    ret
