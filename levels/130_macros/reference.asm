%macro sys_write 3              ; load in an order that can't clobber the arguments
    mov rdx, %3
    mov rsi, %2
    mov edi, %1
    mov eax, 1
    syscall
%endmacro

%macro print 1+                 ; 1+: the last parameter takes the rest of the line
section .rodata
%%str: db %1
%%len equ $ - %%str
section .text
    sys_write 1, %%str, %%len
%endmacro

%macro exit 1
    mov edi, %1
    mov eax, 60
    syscall
%endmacro

global _start

section .text
_start:
    xor eax, eax                ; read(0, buffer, 256)
    xor edi, edi
    mov rsi, buffer
    mov edx, 256
    syscall
    mov rbx, rax                ; keep the count: the macros use rax
    print "you said: "
    sys_write 1, buffer, rbx
    print 10
    print "bye", 10
    exit 0

section .bss
buffer: resb 256
