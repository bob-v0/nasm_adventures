# Level 150 — Jump Tables

*Every interpreter, every `switch` with many cases, and every virtual function call
is an indirect jump.*

## Lesson: jumping through a table

A normal jump has its target written into the instruction. An **indirect jump** reads
its target from a register or from memory, so the program can decide at run time
where to go. A **jump table** is an array of code addresses: index it, and jump to
whatever address you find there:

```
    cmp eax, 10
    ja .bad_opcode              ; ALWAYS bounds-check first
    jmp [table + rax*8]         ; jump to the address stored in table[rax]

section .data
table: dq op_halt, op_push, op_add, ...    ; addresses of labels
```

Without the bounds check, an attacker who controls `rax` controls where your program
jumps. Real exploits have used exactly that.

A label inside `dq` is just its address. One NASM detail: `.local` labels belong to the
last ordinary label, so a `.halt` written under `table:` would mean `table.halt`. Give
handlers ordinary names (`op_halt:`) or write the full name.

## Lesson: a stack machine

The VM (virtual machine) you'll build keeps its values on a **stack**: a pile where
you can only add (**push**) or remove (**pop**) at the top. Here the stack is the
array `vstack`, with a depth counter in a register. Each operation pops its inputs
and pushes its result. The bytecode `PUSH 2, PUSH 3, ADD, PUSH 7, MUL, HALT`
computes (2 + 3) × 7:

```
instruction    stack afterwards (top on the right)
PUSH 2         2
PUSH 3         2 3
ADD            5
PUSH 7         5 7
MUL            35
HALT           35          -> result: 35, depth 1
```

It's the same idea as the JVM, WebAssembly and Python's bytecode.

## Gate

The game provides `code` (the program, 64 bytes) and `vstack` (32 qwords). Interpret
the program from `code[0]`:

| Op | Bytes | Effect (stack top on the right) |
|---|---|---|
| 0 HALT | 1 | stop |
| 1 PUSH v | 2 | push v (a signed byte, sign-extended) |
| 2 ADD / 3 SUB / 4 MUL | 1 | a b → a+b / a−b / a×b (mod 2⁶⁴) |
| 5 DUP | 1 | a → a a |
| 6 SWAP | 1 | a b → b a |
| 7 DROP | 1 | a → |
| 8 OVER | 1 | a b → a b a |
| 9 ROT | 1 | a b c → b c a |
| 10 JNZ off | 2 | pop v; if v ≠ 0, jump by `off` (signed byte) from the *next* instruction |

When the program stops:

| Outcome | `rax` | `rbx` | `rcx` |
|---|---|---|---|
| HALT | top of stack (0 if empty) | 0 | stack depth |
| opcode > 10 | 0 | 1 | depth |
| not enough values to pop | 0 | 2 | depth |
| a push would exceed 32 values | 0 | 3 | depth |

Constraint: at most 120 instructions.
