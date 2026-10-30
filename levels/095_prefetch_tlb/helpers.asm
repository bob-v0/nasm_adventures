; Level 95: the node pool (4 MiB) and the list heads. A node: dq next, dq value
; (64 bytes apart). The game scatters each list's nodes all over the pool.
global pool, heads
POOL_SIZE equ 4 << 20
section .bss
alignb 2 << 20
pool:  resb POOL_SIZE
heads: resq 8
