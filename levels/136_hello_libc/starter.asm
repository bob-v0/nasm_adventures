; Level 136 — Hello, libc
;
; Read n (1..20) with scanf("%ld"), then printf for i = 1..n: "%2ld %4ld %6ld\n"
; (i, i*i, i*i*i), then "sum of cubes: %ld\n". Return 0 from main.

extern printf
extern scanf
global main

section .text
main:
    ; TODO
    xor eax, eax
    ret

section .rodata
