; Level 99 — Measuring
;
; ring_measure(fn): how many cycles does one call of fn take? (fn is an ordinary
; function with no arguments.) Return the answer in rax.
;
; This version times a single call with two rdtsc's. For a chain of 60 multiplies
; (about 180 cycles of work) it says 38. Make it reliable.

global ring_measure

section .text
ring_measure:                   ; rdi = the function
    push rbx
    push r12
    mov rbx, rdi
    rdtsc
    shl rdx, 32
    or rax, rdx
    mov r12, rax
    call rbx
    rdtsc
    shl rdx, 32
    or rax, rdx
    sub rax, r12
    pop r12
    pop rbx
    ret
