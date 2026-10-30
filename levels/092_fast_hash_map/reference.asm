; Level 92 — Fast Hash Map (reference)
;
; - Fibonacci hashing: multiply by 2^64/phi, keep the TOP 13 bits. Every key bit
;   influences them, so counters, aligned addresses and random keys all spread evenly.
; - 8192 slots for at most 4096 keys: load factor <= 1/2, probe chains stay short.
; - A slot is 16 bytes (key next to value): a hit costs one cache line. Linear probing
;   walks neighbouring slots, usually in the same line.
; - Inlined probing, no call: the common case is a few instructions.

global map_init, map_put, map_get

SLOTS equ 8192
SHIFT equ 64 - 13
PHI   equ 0x9E3779B97F4A7C15

section .text
map_init:
    ret

map_put:                        ; rdi = key, rsi = value
    mov rax, PHI
    imul rax, rdi
    shr rax, SHIFT
    shl rax, 4                  ; byte offset of the first slot
    lea rcx, [table]
.probe:
    mov rdx, [rcx + rax]
    cmp rdx, rdi
    je .set
    test rdx, rdx
    jz .claim
    add rax, 16
    and eax, SLOTS * 16 - 1
    jmp .probe
.claim:
    mov [rcx + rax], rdi
.set:
    mov [rcx + rax + 8], rsi
    ret

map_get:                        ; rdi = key -> rax = value or 0
    mov rax, PHI
    imul rax, rdi
    shr rax, SHIFT
    shl rax, 4
    lea rcx, [table]
.probe:
    mov rdx, [rcx + rax]
    cmp rdx, rdi
    je .found
    test rdx, rdx
    jz .absent
    add rax, 16
    and eax, SLOTS * 16 - 1
    jmp .probe
.found:
    mov rax, [rcx + rax + 8]
    ret
.absent:
    xor eax, eax
    ret

section .bss
alignb 64
table: resq 2 * SLOTS
