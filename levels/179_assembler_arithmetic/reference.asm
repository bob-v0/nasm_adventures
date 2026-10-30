mov rax, SQUARE_COUNT
mov rbx, POEM_LEN
mov rcx, 7 * 24 * 60 * 60
mov rdx, ruler_end - squares

section .data
squares:
%assign i 0
%rep 16
    dq i * i
    %assign i i + 1
%endrep
SQUARE_COUNT equ ($ - squares) / 8

poem:     db "Level 179: the assembler counts, so you never have to count again"
POEM_LEN  equ $ - poem

ruler:    times 40 db '-'
          db 10
ruler_end:
