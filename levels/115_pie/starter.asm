; Level 115 — Position Independence
;
; This program works as an ordinary (fixed-address) executable. Make it a PIE:
; it's linked with `gcc -pie`, so it must not contain a single absolute address in
; code or read-only data.
;
; For each argument (a digit 0..6), print the day's name, then "  work" or "  rest"
; (Saturday and Sunday are rest days), each with puts.

extern puts
global main

section .text
main:                           ; main(argc, argv)
    push rbx
    push r12
    push r13
    mov r12d, edi
    mov r13, rsi
    mov ebx, 1
.next:
    cmp ebx, r12d
    jge .done
    mov rax, [r13 + rbx*8]      ; argv[i]
    movzx eax, byte [rax]
    sub eax, '0'
    mov rdi, [days + rax*8]
    call puts
    mov rax, [r13 + rbx*8]      ; (rax didn't survive the call)
    movzx eax, byte [rax]
    sub eax, '0'
    jmp [kinds + rax*8]
.weekday:
    mov edi, work
    jmp .print
.weekend:
    mov edi, rest
.print:
    call puts
    inc ebx
    jmp .next
.done:
    xor eax, eax
    pop r13
    pop r12
    pop rbx
    ret

section .rodata
kinds: dq main.weekday, main.weekday, main.weekday, main.weekday, main.weekday
       dq main.weekend, main.weekend
days:  dq mon, tue, wed, thu, fri, sat, sun
mon: db "Monday", 0
tue: db "Tuesday", 0
wed: db "Wednesday", 0
thu: db "Thursday", 0
fri: db "Friday", 0
sat: db "Saturday", 0
sun: db "Sunday", 0
work: db "  work", 0
rest: db "  rest", 0
