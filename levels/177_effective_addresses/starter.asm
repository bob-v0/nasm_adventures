; Level 177 — The Address Machine
;
; grid: 8x8 qwords, row-major.  On entry: rdi = row (0-6), rsi = col (0-7) (keep both)
;   (row stops at 6: rcx below reads the next row, and row 7 has none)
;   rax = grid[row][col]
;   rbx = address of grid[row][col]
;   rcx = grid[row+1][col]
;   r8  = row*5 + 3 (one lea)

