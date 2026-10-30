# Level 174 — Debugger Eyes

*A vault computes a key, holds it in a register for a single instruction, then wipes
it and tells you there is nothing to see. There is.*

## Lesson: watching a program run

A **debugger** pauses a program and lets you inspect it: one instruction at a time,
or stopping at a **breakpoint** you set. Three tools, from simplest to most capable:

**objdump** shows the code without running it. In {{terminal}}:

```
objdump -d -M intel ./vault
  401000:  4c 8b 24 25 00 20 40 00    mov r12, QWORD PTR ds:0x402000
  ...      address   instruction bytes   the decoded instruction
```

**The game's debugger** ({{debug}}) can run any program, and step backwards. Choose
`program: vault` as what to run. It shows the disassembly, registers and memory. Set a
breakpoint at an address such as `*0x401040`, continue to it, and read the registers.
**back** undoes a step. (From a plain terminal: `ring debug --binary vault`, then
`dis 30`, `break *0x401040`, `c`, `regs`, `back`.)

**gdb** is the standard debugger on Linux, worth learning now. In {{terminal}}:

```
gdb ./vault
(gdb) set disassembly-flavor intel
(gdb) starti                   # stop before the very first instruction
(gdb) x/30i $rip               # disassemble 30 instructions
(gdb) break *0x401040
(gdb) continue
(gdb) info registers r12
(gdb) stepi                    # one instruction
(gdb) x/4gx 0x402000           # 4 qwords in hex
```

For a gdb cheat sheet, see {{docs gdb}}. gdb needs an x86-64 machine (on Apple
Silicon it can't run the vault); the game's debugger works everywhere.

## Gate

When you opened this level, the game built a file `vault` in your level174 folder. Its key is unique to you.
The vault computes a 64-bit key in `r12`, then executes `xor r12, r12` to wipe it.
The key never appears in memory.

1. Find the key with a debugger. You won't find it by reading the source.
2. Write a program that writes the key's **8 bytes** to stdout (in x86 memory
   order, as `dq` stores it) and exits with status 0.

Constraint: at most 20 instructions.

*The vault's source is in the game's repository, and its algorithm is not secret.
Reading it would only teach you to read; the gate is about learning to see.*
