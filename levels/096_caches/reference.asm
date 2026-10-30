; Level 96 — Caches (reference)
;
; Naively, dst is written down a column: every store touches a new cache line, 1 KiB
; (n*8 bytes) after the last, and with n = 128 those lines all fall into the same few
; L1 sets, so each line is evicted before the next column could use it.
; Blocked: transpose 8x8 tiles. A tile reads 8 lines of src and writes 8 lines of dst,
; each of them completely, while all 16 are in L1.

global ring_transpose

B equ 8

section .text
ring_transpose:                 ; rdi = dst, rsi = src, rdx = n
    push rbx
    push r12
    push r13
    push r14
    push r15
    lea r15, [rdx*8]            ; bytes per row
    xor r8d, r8d                ; tile row
.tile_row:
    cmp r8, rdx
    jae .done
    xor r9d, r9d                ; tile column
.tile_col:
    cmp r9, rdx
    jae .next_tile_row
    lea r12, [r8 + B]           ; i_end = min(r8 + B, n)
    cmp r12, rdx
    cmova r12, rdx
    lea r13, [r9 + B]           ; j_end = min(r9 + B, n)
    cmp r13, rdx
    cmova r13, rdx
    mov r10, r8                 ; i
.i:
    mov rax, r10                ; &src[i][r9]
    imul rax, r15
    lea rbx, [rsi + rax]
    mov rax, r9                 ; &dst[r9][i]
    imul rax, r15
    lea r14, [rdi + rax]
    lea r14, [r14 + r10*8]
    mov r11, r9                 ; j
.j:
    mov rax, [rbx + r11*8]
    mov [r14], rax
    add r14, r15                ; next row of dst
    inc r11
    cmp r11, r13
    jb .j
    inc r10
    cmp r10, r12
    jb .i
    add r9, B
    jmp .tile_col
.next_tile_row:
    add r8, B
    jmp .tile_row
.done:
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbx
    ret
