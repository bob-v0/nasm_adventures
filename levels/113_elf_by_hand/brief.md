# Level 113 — ELF by Hand

*No linker this time. You write every byte of the file, including the parts that only the
kernel ever reads.*

## Lesson: what execve reads

An executable is an **ELF** file (Executable and Linkable Format). Before running
anything, `execve` reads two kinds of structure from it:

- the **ELF header**, 64 bytes at offset 0: "this is a 64-bit x86-64 executable, start
  at this address, the program headers are there";
- the **program headers** (56 bytes each): "map these bytes of the file at this virtual
  address, with these permissions". Each `PT_LOAD` header is a **segment**.

Everything else is for other tools. **Section headers** (`.text`, `.data`, `.symtab`…)
exist for linkers and debuggers; the kernel ignores them, and a file can have none.

| ELF header field | size | value here |
|---|---|---|
| `e_ident` | 16 | `7F 'E' 'L' 'F'`, class 2 (64-bit), data 1 (little-endian), version 1, OS ABI 0, 8 zero bytes |
| `e_type` | 2 | 2 = `ET_EXEC` (3 = `ET_DYN`, a PIE or shared library) |
| `e_machine` | 2 | 0x3E = x86-64 |
| `e_version` | 4 | 1 |
| `e_entry` | 8 | the virtual address of the first instruction |
| `e_phoff` | 8 | the **file offset** of the program headers |
| `e_shoff` | 8 | the file offset of section headers (0: none) |
| `e_flags` | 4 | 0 |
| `e_ehsize`, `e_phentsize`, `e_phnum` | 2 each | 64, 56, the number of program headers |
| `e_shentsize`, `e_shnum`, `e_shstrndx` | 2 each | 0 |

| program header field | size | meaning |
|---|---|---|
| `p_type` | 4 | 1 = `PT_LOAD` |
| `p_flags` | 4 | 4 = read, 2 = write, 1 = execute |
| `p_offset` | 8 | where the segment starts in the **file** |
| `p_vaddr`, `p_paddr` | 8 each | where it goes in **memory** (`p_paddr` is unused: same value) |
| `p_filesz`, `p_memsz` | 8 each | bytes taken from the file, and bytes in memory (more = zero-filled, like .bss) |
| `p_align` | 8 | 0x1000: offset and address must agree modulo the page size |

## Lesson: nasm -f bin

`nasm -f bin` writes your bytes as they are: no headers, no sections, no relocations.
Two numbers describe every byte, and it's easy to mix them up:

- its **file offset**: where it is in the file (the first byte is at 0);
- its **virtual address**: where it will be in memory once the file is mapped.

`org 0x400000` tells NASM where the file will be in memory, so labels have their
run-time values: `dq _start` is the entry address. `$$` is the address of the file's first
byte, so `label - $$` is a **file offset**, and `FILE_SIZE equ $ - $$` at the very end is
the file's size.

The simplest layout maps the whole file, headers included, as one segment:

![The starter's layout: ELF header at offset 0, program header at 64, code at 120; one PT_LOAD maps it all at 0x400000](elf-layout.svg)

## Gate

Fill in the headers in the starter so that the file runs: it writes `hand-made` and a
newline, and exits with **42**. The file must be at most **256 bytes**. The audit reads
your file the way the kernel does and names the first field it doesn't accept. (A tidy
version is about 160 bytes. People have squeezed working x86-64 ELF files below 100
bytes by overlapping the headers with each other and with code.)

This is a native level. In the {{terminal}}: `xxd solution` shows your bytes,
`readelf -h -l solution` decodes them.
