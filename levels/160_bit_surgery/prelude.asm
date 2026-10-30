; Provided by level 160: two 256-bit sets, bit i of the set = bit (i % 64) of qword i / 64.
section .data
setA: times 4 dq 0
setB: times 4 dq 0
