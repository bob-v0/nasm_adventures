# Level 178 — Backwards Bytes

*A message arrives from another machine, and all its numbers look wrong.*

## Lesson: little-endian

Memory is a long row of bytes, but registers hold 2-, 4- and 8-byte values. When x86
stores a multi-byte value it puts the **least significant byte at the lowest
address**. This is called **little-endian**:

```
mov dword [x], 0x11223344

address:  x+0  x+1  x+2  x+3
byte:      44   33   22   11
```

Loading does the reverse, so storing and loading round-trip and you rarely notice.
You notice when bytes come from somewhere else. Network protocols and many file
formats are **big-endian** (most significant byte first, also called "network byte
order"). If you load those bytes with a plain `mov`, the value comes out backwards.

You already met this in level 182: `'NASM'` equals `0x4D53414E` because `'N'` (0x4E)
is the low byte, and it lands at the lowest address.

## Lesson: reversing bytes

- `bswap ecx` / `bswap rdx` reverse the 4 or 8 bytes of a register.
- 16 bits: `bswap` has no 16-bit form. Swap the two halves instead: `xchg al, ah`.

## Gate

The game provides a 16-byte big-endian `packet` (filled in by each test) and a
4-byte `seq_out`:

```
offset  size  field
0       2     magic
2       2     length
4       4     sequence
8       8     timestamp
```

When your code finishes:

| Register / memory | Must hold |
|---|---|
| `rax` | magic as a normal number (zero-extended) |
| `rbx` | length (zero-extended) |
| `rcx` | sequence |
| `rdx` | timestamp |
| `seq_out` | sequence, stored in x86 byte order |
| `r8` | the first 8 bytes of the packet loaded with one plain `mov`, to see what "wrong" looks like |

Constraints: at most 12 instructions; must use `bswap`; no shifts, rotates or bitwise
operations.
