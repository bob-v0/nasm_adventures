; echo ARGS...: prints its arguments separated by spaces, then a newline.
%include "_common.inc"
global _start
section .text
_start:
    lea r12, [rsp + 16]         ; argv[1]
    xor r13d, r13d              ; printed anything yet?
.next:
    mov rsi, [r12]
    test rsi, rsi
    jz .done
    test r13d, r13d
    jz .word
    WRITE 1, space, 1
.word:
    mov rsi, [r12]
    xor edx, edx
.len:
    cmp byte [rsi + rdx], 0
    je .print
    inc rdx
    jmp .len
.print:
    WRITE 1, rsi, rdx
    mov r13d, 1
    add r12, 8
    jmp .next
.done:
    WRITE 1, newline, 1
    EXIT 0
section .data
space:   db " "
newline: db 10
