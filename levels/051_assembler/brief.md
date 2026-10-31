# Level 51 — Assembler ★

*For 133 levels NASM has turned your text into bytes. Now you replace it, for a subset
of x86-64 large enough to write real programs in.*

## The job

Read source text from stdin (at most 64 KiB) and write the machine code to stdout, like
`nasm -f bin` with origin 0.

The game decodes your bytes and compares, instruction by instruction, what they do. So
any valid encoding counts: short or near jumps, `83` or `81` immediates, `B8+r` with a
64-bit immediate or `C7`. What must match: exactly the instructions of the source, in
order, with every label resolved.

## The language

It's level 54's output, line by line, plus **labels**:

```
start:
    lea rsi, [rel start]
again:
    inc eax
    cmp eax, 0xa
    jne again
    mov qword [rbx+rcx*8+0x10], -0x1
    call start
```

- A line is empty, a label (`name:`, made of letters, digits and `_`), or one
  instruction. Lines may start with spaces. There are no comments.
- Instructions, registers, operand order and size keywords are exactly as in level 54's
  subset: add, or, and, sub, xor, cmp, mov, test, lea, inc, dec, push, pop, jmp, call,
  the 16 jcc, ret, nop, syscall; 64-bit and 32-bit registers.
- Numbers are `0x` hex, optionally negative (`-0x80`).
- Branch operands and `[rel ...]` name labels. A label may come after its use.

## Everything in the arc

- **Encoding** (57, 56): REX, opcode, ModRM, SIB, displacement, immediate. rsp and r12
  as a base need a SIB; rbp and r13 need a displacement even when it's 0.
- **Decoding** (55, 54): run your output through level 54's disassembler to debug it.
- **Fix-ups** (53): a forward reference needs the address of something not yet
  assembled. Two passes: the first computes every label's address, the second emits.
  That only works if no instruction's size depends on a label it uses, so pick sizes
  that don't (rel32 jumps, disp32 for `[rel ...]`). Real assemblers start with short
  jumps and grow the ones that don't reach, repeating until nothing changes ("branch
  relaxation"). That's why NASM's jumps may be shorter than yours.
- **rip-relative** (54): the displacement counts from the **end** of the instruction,
  after any immediate. Leave a placeholder and patch it once you know the length.

## Gate

Seven named programs and six random ones of 15 to 50 instructions with labels: every
instruction must decode to what the source says, with nothing missing or extra, and the
program must exit with status 0.
