; Provided by level 151.
section .data
src:  times 32 db 0
dst:  times 33 db 0         ; one spare byte: the tests check it is never written
nums: times 16 dq 0
buf:  times 16 db 0
fill: times 16 db 0         ; right after buf
