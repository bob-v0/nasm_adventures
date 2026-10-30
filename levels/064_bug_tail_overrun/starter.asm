; Level 64 — Tail Overrun
;
; ring_strlen(s): the length of the NUL-terminated string s, 16 bytes at a time.
;
; Bug report: it crashes, rarely, on short strings near the end of a buffer. Never in
; the tests the author ran. Find a string length that crashes it when the game puts
; the string right at the end of a page with nothing mapped after it
; (;! witness n = <length>), then fix it, keeping it fast (0.35 cycles per byte).

global ring_strlen

section .text
ring_strlen:                    ; rdi = s
    mov rax, rdi
    pxor xmm1, xmm1             ; zeros, to compare with
.block:
    movdqu xmm0, [rax]          ; 16 bytes of the string
    pcmpeqb xmm0, xmm1
    pmovmskb edx, xmm0          ; bit i: byte i is the NUL
    test edx, edx
    jnz .found
    add rax, 16
    jmp .block
.found:
    tzcnt edx, edx
    add rax, rdx
    sub rax, rdi                ; the NUL's address − s
    ret
