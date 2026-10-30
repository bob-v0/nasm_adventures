# NASM Adventures — the official way to play.
#   docker build -f docker/Dockerfile -t nasm-adventures .
#   docker run --rm -it -v ~/nasm-adventures:/workspace nasm-adventures
FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends nasm binutils gdb python3 python3-venv \
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
CMD ["bash", "-c", "ring status; exec bash"]
