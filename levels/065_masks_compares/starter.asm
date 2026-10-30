; Level 65 — Masks & Compares
;
; ring_memchr(buf, byte, n): the index of the first occurrence of byte (0..255) among
; the n bytes at buf, or −1 if there's none. (The bytes after the n-th don't count, even
; if they match.)
;
; This works, one byte at a time: about 1.3 cycles per byte searched. The budget is 0.3:
; compare 16 at a time.

global ring_memchr

section .text
ring_memchr:                    ; rdi = buf, esi = byte, rdx = n
    xor eax, eax
.next:
    cmp rax, rdx
    jae .none
    cmp [rdi + rax], sil
    je .found
    inc rax
    jmp .next
.none:
    mov rax, -1
.found:
    ret
