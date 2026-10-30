LIMIT = 256


def fixed_tests(ctx):
    return [{"name": "runs", "expect": {"stdout": "hand-made\n", "exit": 42}}]


def audit(build):
    """Read the file the way the kernel does, and explain what's wrong first."""
    import struct
    data = build.elf.read_bytes()
    out = [(f"the file is at most {LIMIT} bytes", len(data) <= LIMIT, f"it's {len(data)}")]
    problems = []
    if data[:4] != b"\x7fELF":
        problems.append("it doesn't start with the magic bytes 7F 'E' 'L' 'F'")
    elif len(data) < 64:
        problems.append(f"the file is {len(data)} bytes, but the ELF header alone is 64")
    elif data[4] != 2 or data[5] != 1:
        problems.append("EI_CLASS must be 2 (64-bit) and EI_DATA 1 (little-endian)")
    else:
        e_type, e_machine, _, entry, phoff = struct.unpack_from("<HHIQQ", data, 16)
        phentsize, phnum = struct.unpack_from("<HH", data, 54)
        if e_type not in (2, 3):
            problems.append(f"e_type is {e_type}; an executable is 2 (ET_EXEC)")
        if e_machine != 0x3E:
            problems.append(f"e_machine is {e_machine:#x}; x86-64 is 0x3E")
        if phentsize != 56 or phnum < 1 or phoff + 56 * phnum > len(data):
            problems.append("the program headers (e_phoff, e_phentsize = 56, e_phnum) "
                            "don't describe 56-byte entries inside the file")
        else:
            loads = [struct.unpack_from("<IIQQQQQQ", data, phoff + 56 * i) for i in range(phnum)]
            loads = [p for p in loads if p[0] == 1]
            covering = [p for p in loads if p[3] <= entry < p[3] + p[6]]
            if not loads:
                problems.append("there is no PT_LOAD program header: nothing would be mapped")
            elif not covering:
                problems.append(f"e_entry {entry:#x} isn't inside any PT_LOAD segment")
            elif not covering[0][1] & 1:
                problems.append("the segment holding the entry point isn't executable (p_flags & 1)")
    out.append(("a valid ELF64 executable header", not problems, "; ".join(problems)))
    return out
