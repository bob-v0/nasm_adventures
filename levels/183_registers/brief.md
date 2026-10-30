# Level 183 — Sixteen Registers

*The gate is four slots in a circle, each holding a value. The values must turn.*

## Lesson: the general-purpose registers

x86-64 has sixteen 64-bit general-purpose registers:

```
rax  rbx  rcx  rdx      the original four: accumulator, base, counter, data
rsi  rdi                source index, destination index
rbp  rsp                base pointer, stack pointer
r8   r9   r10  r11      added when the architecture went 64-bit
r12  r13  r14  r15
```

The names are historical. Most instructions accept any register, though some
instructions and conventions still give certain registers special jobs, as you will
see later. **Leave `rsp` alone for now.** It points at the stack, and the gate
checks that it has not changed.

Two more registers are not general-purpose:

- `rip`, the instruction pointer: the address of the next instruction.
- `rflags`: status bits such as "was the last result zero?" (level 169).

## Lesson: copying and swapping

`mov rax, rbx` copies rbx into rax. Afterwards both hold the same value, and the
old contents of rax are gone.

`xchg rax, rbx` swaps the two registers in a single instruction.

## Gate

The tests load `rax`, `rbx`, `rcx` and `rdx` with values A, B, C, D. Rotate them:

```
before:  rax=A  rbx=B  rcx=C  rdx=D
after:   rax=B  rbx=C  rcx=D  rdx=A
```

Constraints: at most 5 instructions, and `rsp` must be unchanged.
Stretch goal: 3 instructions.

Try {{debug}}: step through your code and watch the registers. Changed ones are
highlighted, and **back** undoes a step.
