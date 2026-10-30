; Level 59 — AVX-512
;
; ring_filter(in, n, threshold, out): copy the elements of in[0 .. n−1] (signed
; dwords) that are greater than threshold to out, in order, packed together; return
; how many. Write nothing else to out. in ends right before an unmapped page.
;
; This works, one element at a time: about 4 cycles per element on random data
; (a branch per element, mispredicted half the time). The budget is 0.4; this CPU has
; AVX-512: a compare into a mask register and vpcompressd do 16 at a time.

global ring_filter

section .text
ring_filter:                    ; rdi = in, rsi = n, edx = threshold, rcx = out
    xor eax, eax                ; kept
    test rsi, rsi
    jz .done
.next:
    mov r8d, [rdi]
    cmp r8d, edx
    jle .skip
    mov [rcx + rax*4], r8d
    inc rax
.skip:
    add rdi, 4
    dec rsi
    jnz .next
.done:
    ret
