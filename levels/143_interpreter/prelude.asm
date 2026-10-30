; Provided by level 143.
section .data
program: times 512 db 0         ; NUL-terminated Brainf*** source
input:   times 128 db 0         ; rdx = number of input bytes
tape:    times 4096 db 0        ; the tests fill it with garbage: clear it first
output:  times 512 db 0
