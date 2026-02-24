#!/usr/bin/env python3
"""
nexus.py — infinite socket collapse hub
every connection is a vector. all vectors collapse to one terminal stream.

usage:
  python3 nexus.py              # start hub on :7999
  python3 nexus.py | axis       # collapse directly into axis
  nc localhost 7999             # connect any terminal as a vector
  curl -N localhost:7999/stream # SSE stream (browser/agent)

each connection auto-names itself. messages broadcast to ALL vectors + stdout.
the terminal is the event horizon. everything collapses here.
"""
import asyncio, sys, json, time, os
import asyncio.streams

PORT = int(os.environ.get("NEXUS_PORT", 7999))
COLORS = ['\x1b[35m','\x1b[36m','\x1b[32m','\x1b[33m','\x1b[34m','\x1b[91m','\x1b[92m','\x1b[93m']
RESET  = '\x1b[0m'
BOLD   = '\x1b[1m'
DIM    = '\x1b[2m'

vectors: dict[str, asyncio.StreamWriter] = {}  # name → writer
_color_idx = 0

def next_color():
    global _color_idx
    c = COLORS[_color_idx % len(COLORS)]
    _color_idx += 1
    return c

def log(msg):
    print(msg, flush=True)  # this is the collapse point — stdout → axis

async def broadcast(sender: str, msg: str):
    """send msg to ALL connected vectors except sender"""
    dead = []
    for name, writer in vectors.items():
        if name == sender:
            continue
        try:
            writer.write(f"{DIM}[{sender}]{RESET} {msg}\n".encode())
            await writer.drain()
        except Exception:
            dead.append(name)
    for d in dead:
        vectors.pop(d, None)

async def handle_vector(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """each TCP connection is a new vector collapsing into the hub"""
    global _color_idx
    color  = next_color()
    addr   = writer.get_extra_info('peername')
    # auto-name: ask for name or use addr
    writer.write(f"{BOLD}{color}nexus{RESET} — you are vector {len(vectors)+1}. name? (enter to skip): ".encode())
    await writer.drain()
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=5.0)
        name = raw.decode().strip() or f"v{len(vectors)+1}@{addr[0]}"
    except asyncio.TimeoutError:
        name = f"v{len(vectors)+1}@{addr[0]}"

    vectors[name] = writer
    tag = f"{color}{BOLD}[{name}]{RESET}"

    # announce
    log(f"◎ {tag} connected  ({len(vectors)} vectors active)")
    await broadcast(name, f"⟵ {name} joined the collapse")

    writer.write(f"{DIM}connected as {name} | {len(vectors)} vectors total{RESET}\n".encode())
    await writer.drain()

    try:
        async for line in reader:
            msg = line.decode().strip()
            if not msg:
                continue
            if msg in ('/quit', '/exit', 'exit'):
                break
            # collapse to stdout (→ axis if piped)
            log(f"{tag} {msg}")
            # broadcast to all other vectors
            await broadcast(name, msg)
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    finally:
        vectors.pop(name, None)
        log(f"◌ {tag} disconnected  ({len(vectors)} vectors remain)")
        await broadcast(name, f"⟵ {name} left")
        writer.close()

async def status_loop():
    """every 30s print a pulse so axis knows nexus is alive"""
    while True:
        await asyncio.sleep(30)
        if vectors:
            names = ', '.join(vectors.keys())
            log(f"{DIM}◉ nexus pulse — {len(vectors)} vectors: {names}{RESET}")

async def main():
    server = await asyncio.start_server(handle_vector, '0.0.0.0', PORT)
    log(f"{BOLD}◎ nexus online :{PORT}{RESET}  — infinite vectors collapse here")
    log(f"{DIM}  connect:  nc $(hostname -I | awk '{{print $1}}') {PORT}")
    log(f"  pipe:     python3 nexus.py | axis")
    log(f"  any new socket = new vector. all collapse to this stdout.{RESET}")
    asyncio.create_task(status_loop())
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("\n◌ nexus offline")
