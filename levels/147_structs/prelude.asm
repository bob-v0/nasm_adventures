; Provided by level 147: room for 8 records of 32 bytes, and the list head.
section .data
people: times 8 * 32 db 0
head:   dq 0
