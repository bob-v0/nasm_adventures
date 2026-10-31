# Level 81 — Bug: Weakly-Ordered Stores ◆◆◆

*Level 83 said x86 keeps stores in order. Here's the fine print.*

## Symptoms

A producer fills a 16-qword buffer, then sets `ready` to the round number. A consumer
waits for `ready`, sums the buffer and acknowledges. Plain TSO guarantees this works:
stores become visible in program order, so if the consumer sees the flag, it sees the
data. Then someone made the producer faster by writing the buffer with `movnti`, a
**non-temporal** store. Now the consumer sums stale data.

## Background: non-temporal stores

A non-temporal store tells the CPU "I won't read this soon, don't fill the cache with
it". It goes through a **write-combining buffer**, which collects the writes to a line
and sends them to memory in one burst, bypassing the cache. That's great for streaming
large amounts of data: `memcpy` and `memset` use them for big copies.

They're also **weakly ordered**: unlike ordinary stores, they may become visible
**after later stores**. TSO's "stores in order" promise doesn't cover them. The two kinds
of store take different roads to memory:

```
ordinary store   ──▶ [ store buffer ] ──── in program order ────▶ memory
non-temporal     ──▶ [ write-combining buffer ] ── whenever ────▶ memory
```

So the flag, an ordinary store, can reach the consumer before the data it announces.

## Background: sfence

`sfence` makes every earlier store visible, non-temporal ones included, before any later
store. It's the fence for exactly this pattern: write-combining data, then `sfence`,
then publish. `mfence` and locked instructions would do too, but cost more. (Other
weakly-ordered operations on x86: `clflushopt`/`clwb` for persistent memory, string
stores with fast `rep movs` in some forms, and the `WC` memory type used for video
memory.)

## Gate

1. Add a witness: a schedule under which the consumer sums stale data:
   `;! witness schedule = N`.
2. Fix it, changing **1 line**.
