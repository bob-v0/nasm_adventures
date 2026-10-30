; Level 177 — The Address Machine
;
; grid: 8x8 qwords, row-major.  On entry: rdi = row, rsi = col (keep both)
;   rax = grid[row][col]
;   rbx = address of grid[row][col]
;   rcx = grid[row+1][col]
;   r8  = row*5 + 3 (one lea)

