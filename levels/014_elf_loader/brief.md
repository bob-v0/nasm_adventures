# Level 14 — ELF Loader

*The programs you wrote in Arc I ran on Linux. Now they run on your kernel, the same
bytes, unchanged.*

## The task

The game gives the kernel an **ELF64 executable**, the file `ld` writes, and sometimes
input for it (the program's stdin). The starter makes the new address space and, once
the program is loaded, jumps to its entry point in ring 3. Yours are the two steps in
between:

- `load_elf`: check it really is an x86-64 executable, then map and fill each
  **PT_LOAD** segment, and return the entry point. Return 0 for anything else, and the
  starter prints `exec failed: not an x86-64 executable this kernel can load`;
- `make_stack`: build the stack Linux gives a new program, and return its rsp.

The tests run Arc I's own programs, built exactly as those levels built them: level 175's
greeting (stdout and stderr), 171's echo (reading stdin), 172's and 173's bug fixes.
There's also a program that checks its argc, argv, `.data` and a 64 KiB `.bss`, plus two
files that aren't executables at all.

## Lesson: what's in an ELF file

![An ELF file's segments, mapped into memory](elf.svg)

The **ELF header** (64 bytes) says what the file is: magic `0x7F E L F`, 64-bit (byte 4 =
2), little-endian (byte 5 = 1), an executable (type 2 at offset 16), for x86-64 (machine
0x3E at 18), where to start (`e_entry`, at 24), and where the program headers are
(`e_phoff` at 32, each `e_phentsize` bytes at 54, `e_phnum` of them at 56).

Each **program header** of type PT_LOAD (1) is one piece of memory to set up:

| offset | | |
|---|---|---|
| 8 | p_offset | where its bytes are in the file |
| 16 | p_vaddr | where they go in memory |
| 32 | p_filesz | how many bytes come from the file |
| 40 | p_memsz | how much memory it takes: the rest is zeros (.bss) |

Map every page from p_vaddr to p_vaddr + p_memsz, copy p_filesz bytes, and leave the rest
zero. Fresh pages already are. Two segments may share a page, so don't map a page twice.

The file comes from outside, so check everything before using it. Every header must lie
inside the file, and every segment inside the program's half. A loader that trusts its
input is how a malicious file takes over a kernel.

## Lesson: the first stack

A Linux program finds its arguments on its stack, not in registers:

```
rsp →  1                   argc
       → "program"         argv[0]
       0                   (end of argv)
       0                   (end of envp: no environment)
       0, 0                (end of the auxiliary vector: AT_NULL)
```

argv[0]'s text ("program") goes on the same page, above these six qwords, and rsp must be
a multiple of 16.

And an **exit status is 8 bits**: `exit(0x5EC2E7)` reports 0xE7. The parent only ever
sees status & 0xFF (level 173's program depends on it). The starter's `exit` already
does this.

## Gate

Every program's output and exit status, exactly, and the bad files refused.
