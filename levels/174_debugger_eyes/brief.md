# Level 174 — Debugger Eyes

*A vault computes a key, holds it in a register for a single instruction, then wipes
it and tells you there is nothing to see. There is.*

## Lesson: watching a program run

A **debugger** pauses a program and lets you inspect it: one instruction at a time,
or stopping at a **breakpoint** you set. Three tools, from simplest to most capable:

**objdump** shows the code without running it:

```
objdump -d -M intel ./vault
  401000:  4c 8b 24 25 00 20 40 00    mov r12, QWORD PTR ds:0x402000
  ...      address   instruction bytes   the decoded instruction
```

**ring debug** is the game's own debugger, with stepping backwards:

```
ring debug --binary vault      # any static x86-64 ELF
(ring) dis 30                  # disassemble 30 instructions from rip
(ring) break *0x401040         # stop when rip reaches this address
(ring) c                       # continue until a breakpoint
(ring) regs                    # all registers; changed ones are marked
(ring) x 0x402000 32           # hex dump of memory
(ring) back                    # undo the last instruction
```

**gdb** is the standard debugger on Linux, worth learning now:

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

`ring docs gdb` has a cheat sheet. gdb needs an x86-64 Linux host. `ring debug` works
everywhere.

## Gate

`ring start` built a file `vault` in your level174 folder. Its key is unique to you.
The vault computes a 64-bit key in `r12`, then executes `xor r12, r12` to wipe it.
The key never appears in memory.

1. Find the key with a debugger. You won't find it by reading the source.
2. Write a program that writes the key's **8 bytes** to stdout (in x86 memory
   order, as `dq` stores it) and exits with status 0.

Constraint: at most 20 instructions.

*The vault's source is in the game's repository, and its algorithm is not secret.
Reading it would only teach you to read; the gate is about learning to see.*
