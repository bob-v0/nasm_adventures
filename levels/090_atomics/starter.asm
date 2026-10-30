; Level 90 — Atomics
;
; Three operations on a shared qword that several threads use at the same time:
;   atomic_fetch_add(addr, n) -> old      *addr += n
;   atomic_swap(addr, v)      -> old      *addr = v
;   atomic_max(addr, v)                   *addr = max(*addr, v)   (unsigned)
; Each must happen as one indivisible step, whatever the other threads do.
; These versions work... with one thread.

global atomic_fetch_add, atomic_swap, atomic_max

section .text
atomic_fetch_add:               ; rdi = address, rsi = amount
    mov rax, [rdi]
    add [rdi], rsi
    ret

atomic_swap:                    ; rdi = address, rsi = new value
    mov rax, [rdi]
    mov [rdi], rsi
    ret

atomic_max:                     ; rdi = address, rsi = value
    cmp [rdi], rsi
    jae .done
    mov [rdi], rsi
.done:
    ret
