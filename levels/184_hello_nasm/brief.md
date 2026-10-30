# Level 184 — Hello, NASM

*You wake as a process with no name, 184 levels above the machine. At the bottom,
level 0, lies ring 0, the privilege level where the code that runs the machine
lives. Each gate on the way down opens only for a program you write yourself.*

## Lesson: what an assembler is

The CPU does not read text. It reads **machine code**, which is just bytes. For example:

```
B8 2A 00 00 00      "put the number 42 into register eax"
```

**Assembly language** gives each instruction a name that people can read.
**NASM** (the Netwide Assembler) turns that text into bytes:

```
mov eax, 42    -->  nasm  -->  B8 2A 00 00 00
```

Every NASM source line has up to four parts, and all of them are optional:

```
label:   mnemonic  operands      ; comment
start:   mov       rax, 42       ; put 42 into rax
```

- A **mnemonic** names the instruction. `mov` means "copy a value into a place".
- **Operands** are written destination first: `mov rax, 42` means `rax = 42`.
- A **label** names a location in the program. You will use labels from level 180 on.
- **Comments** start with `;` and the assembler ignores them. Write lots of them;
  assembly is hard to read without them.
- NASM does not care about upper/lower case in mnemonics and register names
  (`MOV RAX, 42` works). It does care about case in labels.

## Lesson: registers

A **register** is a storage slot inside the CPU. x86-64 has sixteen general-purpose
64-bit registers. You will meet them all in the next level. For now you need two:
`rax` and `rbx`. Think of them as the CPU's only variables, and very fast ones.

## How fragment levels work

In levels 184 to 177 you write only the interesting part. The game wraps your code
in a small program, runs it on an emulated x86-64 CPU starting at your first line,
and stops when execution reaches your last line. Then it checks the registers and
memory.

- `ring test` builds your code and runs the tests you can see.
- `ring submit` also runs hidden tests and opens the next level if everything passes.
- `ring listing` shows the bytes NASM produced for each of your lines. Try it.
- `ring debug` steps through your code one instruction at a time, forwards and backwards.
- `ring docs mov` opens the reference for an instruction.

In the browser these are the **Test** and **Submit** buttons and the **Listing**,
**Reference** and **Debugger** tabs. Click a line number to set a breakpoint.

## Gate

When your code finishes:

- `rax` must hold **42**
- `rbx` must hold **184**

Constraints: at most 4 instructions, and you must use `mov`.
Stretch goal: exactly 2 instructions.

## Try this

Run `ring listing`. NASM encoded your `mov rax, 42` as `B8 2A 00 00 00`, which is
`mov eax, 42`: 5 bytes instead of the 10 that a 64-bit constant needs. That is still
correct, and level 181 explains why.
