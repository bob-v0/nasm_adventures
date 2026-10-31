# Level 184 — Hello, NASM

*You wake as a process with no name, 184 levels above the machine. At the bottom,
level 0, lies ring 0, the privilege level where the code that runs the machine
lives. Each gate on the way down opens only for a program you write yourself.*

## Lesson: what an assembler is

The CPU cannot read text. It reads **machine code**: plain bytes, where each
instruction is a short pattern of bytes. For example:

```
B8 2A 00 00 00      "put the number 42 into register eax"
```

Nobody wants to write programs as hex bytes. **Assembly language** gives every
instruction a short, readable name instead. An **assembler** translates that text
into the bytes. The one you will use is **NASM** (the Netwide Assembler):

```
mov eax, 42    -->  nasm  -->  B8 2A 00 00 00
```

Each line of assembly is usually one instruction, and each instruction does one
small thing.

## Lesson: the parts of a line

A NASM line has up to four parts. Every part is optional:

```
label:   mnemonic  operands      ; comment
start:   mov       rax, 42       ; put 42 into rax
```

- The **mnemonic** names the instruction. `mov` means "copy a value into a place".
- The **operands** say what it works on. The destination comes first:
  `mov rax, 42` means `rax = 42`.
- A **label** gives a name to a place in the program. You will start using labels
  in level 180.
- A **comment** starts with `;` and runs to the end of the line. The assembler
  ignores it. Write plenty: assembly is hard to read without them.

NASM ignores upper and lower case in mnemonics and register names, so
`MOV RAX, 42` works too. Labels are different: `Start` and `start` are two labels.

## Lesson: registers

A **register** is a storage slot inside the CPU itself. Think of registers as the
CPU's variables: there are only a few, and they are very fast. x86-64 has sixteen
general-purpose registers of 64 bits each, and you will meet them all in the next
level. For now you need two: `rax` and `rbx`.

## How fragment levels work

In levels 184 to 177 you write only the interesting part, a **fragment**. The game
wraps your code in a small program and runs it on an emulated x86-64 CPU. It starts
at your first line and stops when execution reaches your last line. Then it checks
the registers and memory.

- {{test}} builds your code and runs the tests you can see.
- {{submit}} also runs hidden tests, and opens the next level if everything passes.
- {{listing}} shows the bytes NASM produced for each of your lines. Try it.
- {{debug}} runs your code one instruction at a time, forwards and backwards. In
  the editor, click a line number to set a breakpoint (a place to pause).
- To learn what an instruction does, see {{docs mov}}.

## Gate

When your code finishes:

- `rax` must hold **42**
- `rbx` must hold **184**

Constraints: at most 4 instructions, and you must use `mov`.
Stretch goal: exactly 2 instructions.

## Try this

Open {{listing}}. NASM encoded your `mov rax, 42` as `B8 2A 00 00 00`, which is
the encoding of `mov eax, 42`. That takes 5 bytes instead of the 10 bytes a full
64-bit constant needs, and it still gives the same result. Level 181 explains why.
