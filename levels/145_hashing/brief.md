# Level 145 — Hashing

*Turn any amount of data into one number that changes completely if any bit changes.*

## Lesson: hash functions

A **hash function** maps data of any length to a fixed-size number. Hash tables use it
to pick a slot, file systems and networks to detect corruption. A good one spreads
similar inputs ("abc", "abd") far apart.

**FNV-1a** is a tiny, decent hash: mix in each byte, then multiply by a prime to spread
it across all 64 bits:

```
h = 0xcbf29ce484222325                 ; "offset basis"
for each byte b:
    h = h xor b
    h = h * 0x100000001b3   (mod 2^64)  ; "FNV prime"
```

## Lesson: CRCs and a dedicated instruction

A **CRC** (cyclic redundancy check) treats the data as a huge polynomial and computes a
remainder. It's very good at catching transmission errors. CRC-32C (Castagnoli) is used
by iSCSI, ext4 and Btrfs, and SSE4.2 added an instruction for it:

```
mov ecx, 0xFFFFFFFF
crc32 ecx, byte [rsi]      ; fold in one byte (word/dword/qword forms exist too)
...
not ecx                    ; final inversion
```

A table-driven CRC in software takes several instructions per byte. `crc32` does it in
one, and the qword form does 8 bytes at a time.

## Gate

The game provides `text`: a NUL-terminated string (up to 127 bytes; the NUL isn't
hashed).

| Register | Must hold |
|---|---|
| `rax` | the 64-bit FNV-1a hash of the bytes |
| `rbx` | the CRC-32C of the bytes (zero-extended) |

Constraints: at most 24 instructions; must use `crc32` and `imul`.
