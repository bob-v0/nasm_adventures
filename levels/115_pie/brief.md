# Level 115 — Position Independence

*Run the same program twice and its code sits at two different addresses. Attackers
can't guess where anything is, as long as the program doesn't care where it is either.*

## Lesson: ASLR and PIE

Until now your programs were linked for a **fixed address** (0x400000 and up), and every
`mov edi, label` baked an absolute address into the instruction. Modern Linux loads
programs at a **random** address each run: **ASLR** (address space layout
randomization). An attacker who can't predict where your code and data are has a much
harder time exploiting a bug.

For that, the program must be a **PIE** (position-independent executable): code that
works wherever it's loaded. gcc builds PIEs by default; this level links yours with
`gcc -pie`.

## Lesson: RIP-relative addressing

The load address changes from run to run, but the **distance** between your code and
your data never does:

```
run 1:  code at 0x55d0a3c01000 ──── 0x2000 bytes ────▶ data at 0x55d0a3c03000
run 2:  code at 0x5612f7e4b000 ──── 0x2000 bytes ────▶ data at 0x5612f7e4d000
```

x86-64 can address memory **relative to the next instruction**: `[rel label]` is encoded
as `[rip + distance]`, so it works at any load address. `default rel` at the top of the
file makes every plain `[label]` RIP-relative.

- `lea rdi, [label]` (with `default rel`) instead of `mov edi, label`.
- RIP-relative addressing can't have an index register: `[days + rax*8]` must become
  `lea rcx, [days]` then `[rcx + rax*8]`.
- Calls into shared libraries (`puts` lives in libc, loaded at its own random address)
  go through the **PLT**: `call puts wrt ..plt`. Level 114 opens that box.

## Lesson: relocations

A **relocation** is a note in an object file: "patch this spot with the address of X".
The linker resolves what it can. In a PIE, some spots can only be patched by the
**loader** (`ld.so`), once it has chosen the load address:

- `dq label` in **.data**: fine. The loader adds the load address
  (`R_X86_64_RELATIVE`), and .data is writable anyway.
- `dq label` in **.rodata** or **.text**: the loader must write into memory that should
  be read-only. The linker warns, and marks the file `DT_TEXTREL` ("text relocations"):
  those pages are made writable during loading, can't be shared between processes, and
  some systems refuse such files.
- A table of **offsets** needs no relocation at all: `dd target - table`, then at run
  time `lea rcx, [table]`, `movsxd rdx, [rcx + rax*4]`, `add rdx, rcx`. This is how
  compilers build `switch` jump tables in position-independent code.

## Gate

The starter works as a fixed-address program. Make it a PIE that passes the relocation
audit: it must link with `gcc -pie` with **no text relocations**. It prints, for each
argument (a digit 0–6), the day's name, then `  work` or `  rest`. The audit reads your
ELF file and checks that it's a PIE (ELF type `DYN`) with no `DT_TEXTREL`. Constraint: at
most 45 instructions.

This is a native level: your program runs on the real kernel, so debug it with gdb in the
{{terminal}}. `readelf -d solution` and `readelf -r solution` show what the loader will do.
