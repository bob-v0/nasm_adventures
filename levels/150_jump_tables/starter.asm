; Level 150 — Jump Tables
;
; Interpret the bytecode in `code` using the stack `vstack` (32 qwords).
; Ops: 0 HALT, 1 PUSH v, 2 ADD, 3 SUB, 4 MUL, 5 DUP, 6 SWAP, 7 DROP, 8 OVER,
;      9 ROT, 10 JNZ off      (see the brief for details)
; Result: rax = top (or 0), rbx = status (0 ok, 1 bad opcode, 2 underflow,
;         3 overflow), rcx = stack depth

