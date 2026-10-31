# Level 183 — Sixteen Registers

*The gate is four slots in a circle, each holding a value. The values must turn.*

## Lesson: the general-purpose registers

x86-64 has sixteen 64-bit **general-purpose registers**. "General-purpose" means
you can use them for almost anything:

```
rax  rbx  rcx  rdx      the original four: accumulator, base, counter, data
rsi  rdi                source index, destination index
rbp  rsp                base pointer, stack pointer
r8   r9   r10  r11      added when the architecture went 64-bit
r12  r13  r14  r15
```

The names are historical, left over from the jobs these registers had on the
earliest x86 chips. Today most instructions accept any of them. A few instructions and conventions still give
certain registers special jobs, and you will meet those later.

**Leave `rsp` alone for now.** It points at the stack (a region of memory the
program relies on), and the gate checks that it has not changed.

Two more registers are not general-purpose. You can't use them as variables, but
you will see them in the debugger:

- `rip`, the instruction pointer: the address of the next instruction to run.
- `rflags`: status bits such as "was the last result zero?" (level 169).

## Lesson: copying and swapping

`mov rax, rbx` **copies** rbx into rax. Afterwards both hold the same value, and
whatever rax held before is gone for good.

`xchg rax, rbx` **swaps** the two registers in a single instruction. Nothing is
lost.

## Gate

The tests load `rax`, `rbx`, `rcx` and `rdx` with four values, A, B, C and D.
Rotate them, so that each value moves one register to the left and A wraps around
to the end:

```
before:  rax=A  rbx=B  rcx=C  rdx=D
after:   rax=B  rbx=C  rcx=D  rdx=A
```

![Each value moves one register to the left; A wraps around to rdx](rotate.svg)

Constraints: at most 5 instructions, and `rsp` must be unchanged.
Stretch goal: 3 instructions.

## Try this

Open {{debug}} and step through your code while you watch the registers. Changed
registers are highlighted, and **back** undoes a step.
