import struct


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        magic, length = rng.getrandbits(16), rng.getrandbits(16)
        seq, ts = rng.getrandbits(32), rng.getrandbits(64)
        if i % 4 == 0:
            magic |= 0x8080  # high bits set: catches movsx
        pkt = struct.pack(">HHIQ", magic, length, seq, ts)
        tests.append({
            "name": f"random {i}",
            "mem": [{"sym": "packet", "hex": pkt.hex()}],
            "expect": {"regs": {"rax": magic, "rbx": length, "rcx": seq, "rdx": ts,
                                "r8": struct.unpack("<Q", pkt[:8])[0]},
                       "mem": [{"sym": "seq_out", "u32": seq}]},
        })
    return tests
