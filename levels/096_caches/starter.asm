; Level 96 — Caches
;
; ring_transpose(dst, src, n): dst = the transpose of src, two n x n matrices of qwords
; stored row by row: dst[j][i] = src[i][j]. Correct, and slow for n = 128. Get it under
; 2.5 cycles per element.

global ring_transpose

section .text
ring_transpose:                 ; rdi = dst, rsi = src, rdx = n
    xor r8d, r8d                ; i (row of src)
.row:
    cmp r8, rdx
    jae .done
    xor r9d, r9d                ; j (column of src)
.col:
    cmp r9, rdx
    jae .next_row
    mov rax, r8                 ; src[i][j] is at (i*n + j) * 8
    imul rax, rdx
    add rax, r9
    mov rcx, [rsi + rax*8]
    mov rax, r9                 ; dst[j][i] is at (j*n + i) * 8
    imul rax, rdx
    add rax, r8
    mov [rdi + rax*8], rcx
    inc r9
    jmp .col
.next_row:
    inc r8
    jmp .row
.done:
    ret
