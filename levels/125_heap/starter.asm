; Level 125 — Heap
;
; void *malloc(size_t size)   -> 16-byte aligned block, never overlapping a live one
; void  free(void *ptr)       -> free(NULL) does nothing
; Get memory with brk (12): brk(0) = current end; brk(new_end) grows the heap.

global malloc
global free

section .text
malloc:
    ; TODO
    xor eax, eax
    ret

free:
    ; TODO
    ret
