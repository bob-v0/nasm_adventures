# Level 92 — Fast Hash Map ★

*The last gate of Arc VII. The data structure every program leans on, made fast for
the keys real programs actually use.*

## The task

A map from 64-bit keys (never 0) to 64-bit values (never 0), for up to 4096 keys:

| function | does |
|---|---|
| `map_init()` | called once, before anything else |
| `map_put(key, value)` | inserts, or replaces the value of a key that's already there |
| `map_get(key)` → `rax` | the key's value, or 0 if it isn't there |

The game's harness inserts 1500 pairs (some keys twice), then looks up 3000 keys (half
of them absent), and checks every answer. It uses three kinds of keys: **random**,
**counters** (consecutive integers) and **addresses** (4 KiB-aligned, like pages or big
allocations). On every kind, the whole run must take under **50 cycles per operation**
on the game's CPU, with your data warm in L2 as in a long-running program.

## What the starter gets wrong

It's a reasonable open-addressing table: linear probing over 8192 slots of
`{key, value}`, and it's correct. Its hash is `key & 8191`, the low 13 bits. For
counters that's fine. But for aligned addresses the low 12 bits are always zero:

```
key                key & 8191
0x7F0000001000     4096
0x7F0000002000     0
0x7F0000003000     4096
0x7F0000004000     0
```

Every key starts its search at slot 0 or 4096 and probes past everything inserted
before it. Quadratic time, from a "reasonable" hash.

## Everything from this arc, in one place

- **The hash** must let every key bit affect the slot. A cheap, strong option for
  power-of-two tables is **Fibonacci hashing**: multiply by `0x9E3779B97F4A7C15`
  (2⁶⁴/φ, φ the golden ratio) and keep the **top** bits (`shr` by 64 − 13). The multiply
  carries low bits upwards, so the top bits have seen all of them.
- **Load factor**: keep the table at most half full, and probe chains stay a slot or two
  long.
- **Layout** (level 96): key and value side by side, so a hit touches one 64-byte line,
  and linear probing walks along that same line.
- **Branches** (level 97): found vs absent is unpredictable by nature, so keep the rest
  predictable. Compare against the key first (the common hit), test for empty second.
- **Instruction selection** (level 94): no `div` (with a power-of-two size, `and` does
  it, or wrap the byte offset), and no `call` in the hot path.
- **Measure** (level 99): the report says whether the time goes to mispredictions, cache
  misses or long probe chains.

Real-world maps (SwissTable in Abseil and Rust, F14 in Folly) go further: one byte of
"hash tag" per slot, compared 16 at a time with SIMD. That's Arc IX.
