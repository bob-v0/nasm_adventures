# Level 64 — Bug: Tail Overrun ◆◆

*The fastest strlen reads memory that isn't part of the string. Done right, that's safe
and every C library does it. Done wrong, it crashes once in a million calls.*

## Symptoms

`ring_strlen` finds the NUL 16 bytes at a time, like level 65's memchr. It passes every
test its author wrote. In production it crashes with SIGSEGV, rarely, always on short
strings, always near the end of some buffer.

## Background: pages

Memory is mapped and protected in **pages** of 4096 bytes. Inside a mapped page every
byte is readable, whatever the program thinks it "owns"; one byte past the last mapped
page is a fault. A string that ends near the end of a page may be followed by nothing
at all.

## Background: vector loads past the end

A 16-byte load reads 16 bytes, even when the data ends at the first. Reading bytes that
aren't yours is harmless *if they're mapped*, and you ignore what you read. A strlen
can't know where the buffer ends (that's the point of strlen), so it must make sure the
extra bytes are mapped, and there is one simple guarantee: **an aligned 16-byte block
never crosses a page boundary**, since 4096 is a multiple of 16. If the block contains
one byte of the string, the whole block is in a mapped page.

So fast strlen implementations align *down* to the block containing the first byte and
read whole aligned blocks from there, including a few bytes *before* the string. Those
can contain zeros too, which must be ignored.

(Tools like AddressSanitizer and Valgrind know glibc's strlen does this on purpose and
suppress it. The game's checked allocator in the earlier arcs would have flagged it.)

## Background: masked tails

With AVX-512 the problem goes away differently: masked loads (`vmovdqu8 zmm0{k1}{z}`)
don't fault on masked-off bytes, so a loop can load exactly the bytes it may (level 59).

## Gate

Find a string length that crashes the original when it ends right before an unmapped
page (`;! witness n = …`). Fix it: aligned loads, mask off the bytes before s, and keep
it under **0.35 cycles per byte**. At most 20 changed lines.
