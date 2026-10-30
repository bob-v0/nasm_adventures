# Level 109 — Event Loop

*nginx, Redis, Node.js: one thread serving thousands of connections. They don't poll.
They ask the kernel "wake me when any of these is ready".*

## Lesson: a server socket

```
socket(AF_INET = 2, SOCK_STREAM = 1, 0)   ; (41) a TCP socket: returns an fd
bind(fd, &addr, 16)                       ; (49) claim 127.0.0.1:7000
listen(fd, 16)                            ; (50) accept connections on it
accept4(fd, 0, 0, 0)                      ; (288) a new fd for the next client
```

`struct sockaddr_in` is 16 bytes: `dw 2` (AF_INET), the **port in network byte order**
(big-endian, level 178 says hello), the IPv4 address (127.0.0.1 = `db 127, 0, 0, 1`) and
8 zero bytes. The starter defines it for you. Each accepted client is an ordinary
descriptor: `read` gets what the client sent, `write` sends to it, `close` hangs up.
A `read` of 0 means the client closed its side.

## Lesson: epoll

**epoll** is a kernel object that watches descriptors for you.

1. `epoll_create1(0)` (291) creates it and returns an fd.
2. `epoll_ctl(ep, EPOLL_CTL_ADD = 1, fd, &event)` (233) says "watch fd for these
   events". `EPOLLIN` (1) means "readable": data to read, a connection to accept, or the
   end of the stream.
3. `epoll_wait(ep, events, max, timeout_ms)` (232) **blocks until at least one** watched
   descriptor is ready, then fills `events` with the ready ones and returns how many.
   A timeout of −1 waits as long as it takes.

Each `struct epoll_event` is `dd events` + `dq data`: **12 bytes, packed**, with no padding
on x86-64 (a famous exception to the usual alignment rules). `data` is yours: the kernel
hands it back untouched, so store the fd there.

epoll is **level-triggered** by default: as long as a descriptor has unread data,
`epoll_wait` keeps reporting it. So you can read just once per event and come back for
the rest. Closing a descriptor removes it from the epoll set.

## Lesson: the event loop

```
forever:
    n = epoll_wait(...)
    for each ready event:
        listening socket?  accept, and watch the new client
        a client?          read; echo it back, or close it if read returned 0
```

Nothing ever blocks except `epoll_wait`, so one slow client can't hold up the others.
(Almost: a `write` to a client that doesn't read could block. The boss of this arc deals
with that. Here, messages are small.)

## Gate

An **echo server** on 127.0.0.1:**7000**: everything a client sends comes straight back
to it. Serve any number of clients at the same time; when a client closes its side,
close its connection. The server never exits: the game stops it once every client is
done. The tests use dozens of clients that connect at different times, send in pieces,
and pause. The grader checks that you wait with `epoll_wait` and that no client
connection is left open. Constraint: at most 90 instructions.
