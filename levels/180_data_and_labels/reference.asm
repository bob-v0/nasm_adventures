mov rax, [input]                 ; memory -> register
mov [slot], rax                  ; register -> memory
mov rax, greeting                ; the address itself
movzx ebx, byte [greeting + 7]   ; one byte from memory
mov word [counter], 0xBEEF       ; size needed: no register to infer it from

section .data
greeting: db "Hello, Ring!", 0
counter:  dw 0

section .bss
slot: resq 1
