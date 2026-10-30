; Level 93: the input samples and the output buffer.
global samples, smoothed
section .bss
alignb 64
samples:  resq 4096
smoothed: resq 4096
