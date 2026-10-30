; Provided by level 134: room for the moves (2 bytes each, up to 2^12 - 1 moves).
bits 64
global moves
section .data
moves: times 8192 db 0
