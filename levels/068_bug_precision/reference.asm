; Level 68 — Precision Lost (reference)
;! witness a = "1", b = "1e9", c = "1"
;
; ring_hit(a, b, c, hits): the ray tracer's ray-sphere intersection. A ray meets a
; sphere at the distances t where a·t² + b·t + c = 0 (a is never 0). Returns in rax:
;     2: two hits, stored in hits[0] < hits[1]
;     1: the ray grazes the sphere (b² − 4ac is exactly 0), hits[0] = −b / 2a
;     0: no hit
;    −1: an input is NaN (a broken scene: report it, don't draw it)
; Both hits must be accurate to 12 significant digits.
;
; Bug reports: tiny spheres far away are drawn in the wrong place, and broken scenes
; draw nothing instead of being reported. Find inputs that go wrong, put one in a
; witness line (;! witness a = "1", b = "2", c = "3"), and fix the code.

global ring_hit

section .rodata
four: dq 4.0
half: dq 0.5
minus_half: dq -0.5
align 16
sign: dq 0x8000000000000000, 0

section .text
ring_hit:                       ; xmm0 = a, xmm1 = b, xmm2 = c, rdi = hits
    movapd xmm3, xmm1
    mulsd xmm3, xmm1            ; b²
    movapd xmm4, xmm0
    mulsd xmm4, xmm2
    mulsd xmm4, [rel four]      ; 4ac
    subsd xmm3, xmm4            ; d = b² − 4ac
    pxor xmm5, xmm5
    ucomisd xmm3, xmm5
    jp .nan                     ; unordered: an input was NaN
    jb .none                    ; d < 0: the ray misses
    je .one                     ; d = 0: it grazes
    sqrtsd xmm3, xmm3           ; √d
    movq rax, xmm1
    test rax, rax
    jns .b_positive
    xorpd xmm3, [rel sign]      ; sign(b)·√d (b < 0: −√d)
.b_positive:
    addsd xmm3, xmm1            ; b + sign(b)·√d: same signs, nothing cancels
    mulsd xmm3, [rel minus_half] ; q
    movapd xmm7, xmm3
    divsd xmm7, xmm0            ; q / a
    movapd xmm8, xmm2
    divsd xmm8, xmm3            ; c / q
    movapd xmm9, xmm7
    minsd xmm7, xmm8
    maxsd xmm8, xmm9
    movsd [rdi], xmm7
    movsd [rdi+8], xmm8
    mov eax, 2
    ret
.one:
    movapd xmm7, xmm5
    subsd xmm7, xmm1
    mulsd xmm7, [rel half]
    divsd xmm7, xmm0            ; −b / 2a
    movsd [rdi], xmm7
    mov eax, 1
    ret
.none:
    xor eax, eax
    ret
.nan:
    mov rax, -1
    ret
