; Level 63 — Packed Floats
;
; ring_dot(a, b, n): the dot product a[0]·b[0] + ... + a[n−1]·b[n−1] of two arrays of
; n floats (single precision), returned as a float in xmm0. Both arrays are 16-byte
; aligned. Any order of additions is fine: the result must be within 1e−4 of the exact
; value, relative to the sum of |a[i]·b[i]|.
;
; This works, one float at a time: about 4 cycles per element. The budget is 0.6.

global ring_dot

section .text
ring_dot:                       ; rdi = a, rsi = b, rdx = n
    xorps xmm0, xmm0            ; the sum
    test rdx, rdx
    jz .done
.next:
    movss xmm1, [rdi]
    mulss xmm1, [rsi]
    addss xmm0, xmm1
    add rdi, 4
    add rsi, 4
    dec rdx
    jnz .next
.done:
    ret
