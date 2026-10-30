; Level 59: the input ends right before a page the game unmaps; the output.
global numbers, guard, kept
section .bss
alignb 4096
numbers: resd 16384
guard:   resb 4096
kept:    resd 16384 + 16
