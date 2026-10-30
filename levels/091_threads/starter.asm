; Level 91 — Threads
;
; ring_parallel_sum(values, n, k): the sum of n qwords, computed by k threads (1..8),
; each adding up its own part. Create them with clone (syscall 56), give each its own
; stack, and wait for all of them (futex, syscall 202) before adding up their results.
; This version is correct, but it uses no threads at all.

global ring_parallel_sum

section .text
ring_parallel_sum:              ; rdi = values, rsi = n, rdx = k
    xor eax, eax
    test rsi, rsi
    jz .done
.add:
    add rax, [rdi]
    add rdi, 8
    dec rsi
    jnz .add
.done:
    ret
