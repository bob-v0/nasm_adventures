lea rdx, [rsi + rdi*8]          ; rdx = row*8 + col (element index)
lea rbx, [grid + rdx*8]         ; rbx = &grid[row][col]
mov rax, [rbx]
mov rcx, [rbx + 64]             ; one row = 8 qwords = 64 bytes further
lea r8, [rdi + rdi*4 + 3]       ; row*5 + 3
