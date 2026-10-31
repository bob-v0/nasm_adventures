# Level 108 — Timers

*A client that connects and then says nothing still holds a descriptor, a buffer and a
slot in your tables. Servers can't wait forever; they need to know what time it is.*

## Lesson: time as an event

An event loop sleeps in `epoll_wait`. To do something **later** ("close this client
if it's still silent in 5 seconds"), time itself has to become an event. Linux's
**timerfd** is a timer that looks like a descriptor:

```
timerfd_create(CLOCK_MONOTONIC = 1, 0)            ; (283) returns an fd
timerfd_settime(fd, 0, &spec, 0)                  ; (286) arm it
```

`spec` is a `struct itimerspec`: an **interval** (`dq seconds, nanoseconds`) followed by
the **first expiry** (same format). An interval of 0 fires once. For example, a timer
that first fires after half a second, then every 2 seconds:

```
spec: dq 2, 0               ; interval: every 2 s
      dq 0, 500000000       ; first expiry: in 0.5 s
```

When the timer has fired, the fd is readable: `read(fd, &n, 8)` returns the number of
expirations since the last read (more than 1 if you were late) and resets it. Put it in the epoll set and the
loop wakes for clients **and** for time.

(`epoll_wait`'s timeout argument is the other way to wait for time, in milliseconds.)

## Lesson: which clock

`clock_gettime(CLOCK_MONOTONIC, &ts)` (228, level 117) counts time since an arbitrary
start, and never jumps. `CLOCK_REALTIME` is the wall clock: an administrator or NTP can
set it backwards. Timeouts always use the monotonic clock. (The game's clock is virtual: when your server
and every client are waiting, it jumps straight to the next event. So waiting 5 seconds
costs nothing, and every run is identical.)

## Lesson: many deadlines

Every connection has its own deadline. Options, from simplest:

- **one periodic tick** (say every 100 ms) and a scan of all connections. Simple, and
  accurate to one tick;
- a **timer heap** (a priority queue that always knows the earliest deadline), with the
  timerfd set to that one;
- a **timer wheel**: an array of buckets by expiry time, one bucket per tick. It's O(1)
  to add and remove, which is what the Linux kernel and high-performance servers use.

Any of them passes here.

## Gate

Level 109's echo server, plus an **idle timeout**. A client that has sent nothing for
**5 seconds** (since it connected, or since its last data) receives `timeout` and a
newline, and is disconnected. Accuracy matters: not before 5.0 s, and by 5.2 s. Clients
that keep talking are never cut off. Use a timerfd. The starter is level 109's
reference. Constraint: at most 140 instructions.

*Watch your constants:* 5 seconds is 5 000 000 000 ns, more than fits in a 32-bit
immediate. `cmp rcx, 5_000_000_000` assembles with a warning and compares against
something else.
