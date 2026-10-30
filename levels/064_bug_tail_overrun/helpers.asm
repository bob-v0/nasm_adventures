; Level 64: room for strings, then a page the game unmaps (nothing may read it).
global strings, guard
section .bss
alignb 4096
strings: resb 65536
guard:   resb 4096
