; Level 77 — Lock-Free Stack
;
; A stack shared by several threads, without a lock:
;   stack_push(stack, node)     node: dq next, dq value
;   stack_pop(stack) -> rax     the node on top, or 0 if the stack is empty
; `stack` points to zeroed memory: its first qword can be the top pointer.
; These versions are fine with one thread.

global stack_push, stack_pop

section .text
stack_push:                     ; rdi = stack, rsi = node
    mov rax, [rdi]
    mov [rsi], rax
    mov [rdi], rsi
    ret

stack_pop:                      ; rdi = stack
    mov rax, [rdi]
    test rax, rax
    jz .empty
    mov rdx, [rax]
    mov [rdi], rdx
.empty:
    ret
