# Level 58 — SIMD Gauntlet ★

*Every web browser, every JSON parser, every database checks that its text is valid
UTF-8, gigabytes at a time. The fastest way to do it is a few shuffles per 16 bytes,
and it took until 2021 to find it.*

## The job

`ring_utf8_valid(bytes, n)` returns 1 if the n bytes are valid UTF-8, and 0 if not.

It must run at **4 GB/s**: on the game's 4 GHz CPU that's **1 cycle per byte**, for any
valid text (English, Russian, Chinese, emoji). Invalid text only has to be detected, at
any speed.

## UTF-8

UTF-8 writes each character (a Unicode **code point**, U+0000 to U+10FFFF) as 1 to 4
bytes. The first byte, the **lead**, says how many; the others are **continuation**
bytes, `10xxxxxx`:

| code points | bytes |
|---|---|
| U+0000–007F | `0xxxxxxx` |
| U+0080–07FF | `110xxxxx 10xxxxxx` |
| U+0800–FFFF | `1110xxxx 10xxxxxx 10xxxxxx` |
| U+10000–10FFFF | `11110xxx 10xxxxxx 10xxxxxx 10xxxxxx` |

Example: é is U+00E9 = 00011 101001 in binary, so it's `110 00011` `10 101001` =
`C3 A9`.

Some byte sequences fit the bit patterns and are still **not** valid:

- **overlong** encodings, a character in more bytes than needed: `C0 AF` for '/' (the
  classic security bug), `E0 80..9F`, `F0 80..8F`;
- **surrogates** U+D800–DFFF (`ED A0..BF ..`): UTF-16's business, never characters;
- anything beyond **U+10FFFF** (`F4 90..`), and the bytes `F5`–`FF`, which never appear;
- a lead byte without its continuations, a continuation without a lead, or a text that
  ends inside a character.

## Everything in the arc

- **Masks & compares** (65): a block with no byte ≥ 0x80 is ASCII, valid on its own.
- **Shuffles** (66): `pshufb` is a 16-entry table lookup, done for 16 bytes at once.
  `palignr` builds the "previous byte" of every position from two consecutive blocks.
- **Saturating arithmetic** (67): `psubusb` turns "≥ 0xE0" into "has its top bit".
- **Tails** (64, 59): the bytes after the n-th may be anything, so they must not
  count. Pad, mask, or handle them separately.
- **AVX2 / AVX-512** (62, 59): optional. The SSE version fits the budget; wider is
  faster, and every AVX2 shuffle is two 128-bit ones side by side (60).

## The algorithm

Keiser and Lemire's idea: almost every error is visible in a **pair** of consecutive
bytes, and is decided by just three nibbles (4-bit halves): the high and low nibble of
the first byte, and the high nibble of the second.

1. Give each kind of error its own bit.
2. For each of the three nibbles, make a 16-entry table: for each nibble value, the
   errors it is *compatible with*.
3. Look all three up with `pshufb`, for 16 positions at once, and AND the results. A bit
   that survives is an error.

The hints list the error classes; the paper ("Validating UTF-8 In Less Than One
Instruction Per Byte", 2021) has the tables. Or design your own.

## Gate

- Every valid text at **≤ 1 cycle per byte**, plus a small fixed allowance.
- Every invalid text rejected. The tests include every kind of invalid sequence, in the
  middle, at block boundaries and at the very end, and random bytes.
