# Level 58 — SIMD Gauntlet ★

*Every web browser, every JSON parser, every database checks that its text is valid
UTF-8, gigabytes at a time. The fastest way to do it is a few shuffles per 16 bytes,
and it took until 2021 to find it.*

## The job

`ring_utf8_valid(bytes, n)` returns 1 if the bytes are valid UTF-8 and 0 if not, at
**4 GB/s**: on the game's 4 GHz CPU that's **1 cycle per byte**, for any valid text
(English, Russian, Chinese, emoji). Invalid text only has to be detected.

## UTF-8

| code points | bytes |
|---|---|
| U+0000-007F | `0xxxxxxx` |
| U+0080-07FF | `110xxxxx 10xxxxxx` |
| U+0800-FFFF | `1110xxxx 10xxxxxx 10xxxxxx` |
| U+10000-10FFFF | `11110xxx 10xxxxxx 10xxxxxx 10xxxxxx` |

And what's *not* valid, even when the bit patterns fit:
- **overlong** encodings: a character in more bytes than needed (`C0 AF` for '/', the
  classic security bug; `E0 80..9F`, `F0 80..8F`);
- **surrogates** U+D800-DFFF (`ED A0..BF ..`): UTF-16's business, never characters;
- beyond **U+10FFFF** (`F4 90..`, and the bytes `F5`-`FF` never appear);
- a lead byte without its continuations, a continuation without a lead, a text that
  ends inside a character.

## Everything in the arc

- **Masks & compares** (65): a block with no byte ≥ 0x80 is ASCII, valid on its own.
- **Shuffles** (66): `pshufb` is a 16-entry table lookup, done for 16 bytes at once.
  `palignr` builds the "previous byte" of every position from two consecutive blocks.
- **Saturating arithmetic** (67): `psubusb` turns "≥ 0xE0" into "has its top bit".
- **Tails** (64, 59): the bytes after the n-th may be anything, so they must not
  count; pad, mask or handle them separately.
- **AVX2 / AVX-512** (62, 59): optional. The SSE version fits the budget; wider is
  faster, and every AVX2 shuffle is two 128-bit ones side by side (60).

## The algorithm

Keiser and Lemire's idea: almost every error is visible in a **pair** of consecutive
bytes, and decided by three nibbles: the high and low nibble of the first byte and the
high nibble of the second. Give each kind of error a bit; for each of the three nibbles,
a 16-entry table says which errors that nibble value is *compatible with*. Look all three
up with `pshufb`, AND them: a bit that survives is an error. The hints have the classes;
the paper ("Validating UTF-8 In Less Than One Instruction Per Byte", 2021) has the tables.

Or design your own. The tests include every kind of invalid sequence, in the middle,
at block boundaries and at the end, and texts of every script.

## Gate

Valid texts at **≤ 1 cycle per byte**; every invalid text rejected.
