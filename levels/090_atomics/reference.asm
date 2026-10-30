; Level 90 — Atomics (reference)
global atomic_fetch_add, atomic_swap, atomic_max

section .text
atomic_fetch_add:               ; rdi = address, rsi = amount -> the old value
    mov rax, rsi
    lock xadd [rdi], rax        ; read, add, write, and nothing in between
    ret

atomic_swap:                    ; rdi = address, rsi = new value -> the old value
    mov rax, rsi
    xchg [rdi], rax             ; xchg with memory is always locked
    ret

atomic_max:                     ; rdi = address, rsi = value: *rdi = max(*rdi, value)
    mov rax, [rdi]              ; what we think is there
.retry:
    cmp rax, rsi
    jae .done                   ; already at least as big (unsigned)
    lock cmpxchg [rdi], rsi     ; if still rax: store rsi; else rax = what's there now
    jne .retry
.done:
    ret
