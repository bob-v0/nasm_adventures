# Level 53 — JIT

*Level 150's interpreter spends most of its time deciding what to do next. A JIT decides
once, writes down the answer as machine code, and runs that.*

## The bytecode (level 150)

| Op | Bytes | Effect (stack top on the right) |
|---|---|---|
| 0 HALT | 1 | stop |
| 1 PUSH v | 2 | push v (a signed byte) |
| 2 ADD / 3 SUB / 4 MUL | 1 | a b → a+b / a−b / a×b |
| 5 DUP / 6 SWAP / 7 DROP | 1 | a → a a / a b → b a / a → |
| 8 OVER / 9 ROT | 1 | a b → a b a / a b c → b c a |
| 10 JNZ off | 2 | pop v; if v ≠ 0, jump by off from the next op |

Errors stop the program with rax = 0 and rdx = 1 (opcode > 10, when reached), 2 (not
enough values) or 3 (more than 32). On HALT: rax = the top (0 if empty), rdx = 0.
Always rcx = the depth. Jumps in the tests always land on the start of an op.

## Lesson: memory you can execute

Code is just bytes, but the CPU only runs bytes in pages marked executable. A JIT asks
the kernel for memory, writes code into it, and changes its protection:

```
mmap(0, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0)   ; rax = 9
... write the code ...
mprotect(addr, size, PROT_READ | PROT_EXEC)                                ; rax = 10
call addr + entry
munmap(addr, size)                                                         ; rax = 11
```

**W^X** (write xor execute): memory is never writable and executable at the same time,
so a bug that lets an attacker write memory doesn't also let them write code. Browsers,
iOS and OpenBSD enforce it; the game checks it.

## Lesson: templates

The simplest JIT copies a fixed piece of machine code per op: a **template**. Let NASM
encode them: write the instructions in `.rodata` between labels, and copy the bytes
between two labels (`b_add_end - b_add` is a length NASM computes). The templates only
need patching where a value goes in: PUSH's immediate, and branch offsets.

```
b_add:  mov rax, [rdi + r9*8 - 8]       ; rdi = the VM stack, r9 = the depth
        add [rdi + r9*8 - 16], rax
        dec r9
b_add_end:
```

The interpreter's checks become code too: `cmp r9, 2` / `jb underflow` in front of ADD.

## Lesson: forward jumps

A rel32 is `target − (address after the rel32)`. A JNZ that jumps forward needs the
address of code that doesn't exist yet. With rel32 everywhere every op's code has a fixed
size, so: **pass 1** generates everything and records where each bytecode position's code
starts, **pass 2** generates it again, now with every target known. (Real assemblers do
the same, level 51.)

## Why it's faster

The interpreter pays per op: a load of the opcode, bounds and stack checks, and an
indirect `jmp` the branch predictor keeps getting wrong. The compiled code is a
straight line of the work itself.

## Gate

`ring_run(code)` compiles and runs the program, under **5 cycles per op** executed (plus
the compile time), with W^X.
