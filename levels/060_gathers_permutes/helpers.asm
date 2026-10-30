; Level 60: the sprite row (palette indexes), the palette, and the screen row.
global sprite, palette, screen
section .bss
alignb 64
sprite:  resb 16384
palette: resd 256
screen:  resd 16384 + 16
