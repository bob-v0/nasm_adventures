; Level 95 — Prefetch & TLB
;
; ring_sum_lists(heads, k): k (1..8) linked lists; heads[i] is the first node of list i
; (0: empty). A node is { dq next, dq value }. Return the sum of every value.
; The nodes are scattered over a 4 MiB pool (`pool`, 2 MiB aligned).
; Correct, and slow: about 220 cycles per node. Get it under 45.

global ring_sum_lists
extern pool

section .text
ring_sum_lists:                 ; rdi = heads, rsi = k
    xor eax, eax
    xor ecx, ecx
.list:
    cmp rcx, rsi
    jae .done
    mov rdx, [rdi + rcx*8]
.node:
    test rdx, rdx
    jz .next_list
    add rax, [rdx + 8]
    mov rdx, [rdx]
    jmp .node
.next_list:
    inc rcx
    jmp .list
.done:
    ret
