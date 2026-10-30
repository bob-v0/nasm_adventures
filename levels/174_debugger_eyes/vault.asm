; Level 174 vault. Built per player with -DSEED_A=... -DSEED_B=... -DSEED_C=...
; and stripped. The key lives only in r12, and only for a moment.
; (Level authors: gen.py contains a Python model of this computation.)

bits 64
global _start

section .data
table:  dq SEED_A, SEED_B, SEED_C
msg:    db `vault: key computed and wiped. nothing to see here.\n`
MSG_LEN equ $ - msg

section .text
_start:
    mov r12, [table]
    mov rax, [table + 8]
    xor r12, rax
    rol r12, 13
    add r12, [table + 16]
    mov rcx, 0x9E3779B97F4A7C15
    imul r12, rcx
    mov rdx, r12
    shr rdx, 29
    xor r12, rdx
key_ready:
    nop                         ; <- the key is in r12 here
    xor r12, r12                ; wiped
    xor eax, eax
    xor ecx, ecx
    xor edx, edx
    mov eax, 1
    mov edi, 1
    mov rsi, msg
    mov edx, MSG_LEN
    syscall
    mov eax, 60
    xor edi, edi
    syscall
