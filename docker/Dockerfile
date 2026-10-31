# NASM Adventures — the official way to play.
#   docker build -f docker/Dockerfile -t nasm-adventures .
#   docker run --rm -it -p 127.0.0.1:8080:8080 -v ~/nasm-adventures:/workspace nasm-adventures
# then open the link it prints. For a shell instead: append `bash` to the run command.
FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends nasm binutils gcc libc6-dev gdb strace less xxd qemu-system-x86 python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /opt/nasm_adventures
COPY pyproject.toml ./
COPY ring ./ring
RUN pip install --no-cache-dir . && rm -rf build *.egg-info
COPY levels ./levels

ENV RING_LEVELS=/opt/nasm_adventures/levels \
    RING_WORKSPACE=/workspace

RUN useradd --create-home player && mkdir /workspace && chown player /workspace \
 && printf 'set disassembly-flavor intel\n' > /home/player/.gdbinit
USER player
WORKDIR /workspace
EXPOSE 8080
# Inside the container the server must listen on all interfaces; publish the port on
# 127.0.0.1 only (as above). Access still requires the token in the printed link.
CMD ["ring", "ui", "--host", "0.0.0.0", "--port", "8080", "--no-browser"]
