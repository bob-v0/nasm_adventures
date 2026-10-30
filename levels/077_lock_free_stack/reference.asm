; Level 77 — Lock-Free Stack (reference)
; A Treiber stack (1986): the top pointer is the only shared word, changed only by CAS.
global stack_push, stack_pop

section .text
stack_push:                     ; rdi = stack, rsi = node
    mov rax, [rdi]              ; the top we think it is
.retry:
    mov [rsi], rax              ; node.next = top
    lock cmpxchg [rdi], rsi     ; top = node, if top is still what we read
    jnz .retry                  ; someone changed it: rax = the new top, try again
    ret

stack_pop:                      ; rdi = stack -> rax = node, or 0 if empty
    mov rax, [rdi]
.retry:
    test rax, rax
    jz .empty
    mov rdx, [rax]              ; top.next
    lock cmpxchg [rdi], rdx     ; top = top.next, if top is still rax
    jnz .retry
.empty:
    ret
