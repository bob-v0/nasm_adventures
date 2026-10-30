; Level 66: the buffer the game fills for each test (and some bytes after it).
global buffer
section .bss
alignb 64
buffer: resb 40000
