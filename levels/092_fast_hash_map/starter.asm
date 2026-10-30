; Level 92 — Fast Hash Map (boss)
;
; A map from 64-bit keys (never 0) to 64-bit values (never 0), for up to 4096 keys:
;   map_init()               called once, first
;   map_put(key, value)      insert, or replace the value of an existing key
;   map_get(key) -> rax      its value, or 0 if the key isn't there
;
; This one is an open-addressing table (linear probing) of 8192 slots, and it's
; correct. On random keys it's fine; on the keys real programs use (counters, aligned
; addresses) it crawls. Hit 50 cycles per operation on every kind of key.

global map_init, map_put, map_get

SLOTS equ 8192                  ; slot = dq key, dq value; key 0 = empty

section .text
map_init:
    ret

slot_of:                        ; rdi = key -> rcx = its first slot (the low bits)
    mov rcx, rdi
    and rcx, SLOTS - 1
    ret

map_put:                        ; rdi = key, rsi = value
    call slot_of
.probe:
    mov rax, rcx
    shl rax, 4
    mov rdx, [table + rax]
    test rdx, rdx
    jz .claim
    cmp rdx, rdi
    je .set
    inc rcx
    and rcx, SLOTS - 1
    jmp .probe
.claim:
    mov [table + rax], rdi
.set:
    mov [table + rax + 8], rsi
    ret

map_get:                        ; rdi = key -> rax = value or 0
    call slot_of
.probe:
    mov rax, rcx
    shl rax, 4
    mov rdx, [table + rax]
    test rdx, rdx
    jz .absent
    cmp rdx, rdi
    je .found
    inc rcx
    and rcx, SLOTS - 1
    jmp .probe
.found:
    mov rax, [table + rax + 8]
    ret
.absent:
    xor eax, eax
    ret

section .bss
alignb 64
table: resq 2 * SLOTS
