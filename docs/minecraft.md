# Minecraft 1.8.9 void server

`examples/mc_void.nbl` is a minimal Minecraft Java Edition server for the
Voja4 badge and a W5500 Ethernet module. It targets **1.8.9 / protocol 47**,
the last version with uncompressed chunk packets and without the modern
configuration/registry phases.

## Behavior

- Listens on `192.168.1.50:25565` (static IP, gateway `192.168.1.10`).
- Answers the server-list ping with a MOTD and protocol 47.
- Accepts one vanilla 1.8.9 client connection to a 16x16 stone platform in a
  void world.
- Sends one chunk section at y=64 with a 16x16 stone platform, full
  block/sky light, and the void biome (127).
- Confirms block breaks and placements with `0x23 Block Change`; placement
  always produces stone and supports all six faces.
- Answers keepalives and ignores normal client play packets.

It is **not** a full server: no terrain beyond the platform, no world storage, no encryption, no
compression, no mobs, no inventory, no second player, and no modern-client
support.

## Packet sequence

Serverbound:

1. Handshake (next state 1 for status, 2 for login)
2. Status request, then Ping
3. Login Start
4. Player Digging (`0x07`) and Block Placement (`0x08`)
5. Normal play packets (client settings, position, keepalive, ...)

Clientbound:

1. Status Response, then Pong
2. Login Success
3. Join Game
4. Chunk Data
5. Player Position And Look
6. Block Change (`0x23`) for breaks/placements
7. Keep Alive every few seconds

## Chunk packet

The world is an Overworld chunk with one stone platform:

- Chunk x/z: `0, 0`
- Ground-up continuous: true
- Primary bit mask: `0x0010` (section 4, y=64)
- Data length: `12544` bytes
  - 512 bytes of stone platform block states (`0x10, 0x00` repeated)
  - 7680 bytes of air block data
  - 2048 bytes of full block light (`0xFF`)
  - 2048 bytes of full sky light (`0xFF`)
  - 256 bytes of void biome (`0x7F`)

The complete chunk packet is 12560 bytes. Socket 0 is configured with the
whole 16 KB W5500 TX buffer, so the firmware writes the packet into the TX
buffer in one SPI burst and issues a single `SEND`. Each `SEND` is followed
by an 81 ms settling delay, and closing a socket leaves a longer settling
period before reopening it; both avoid reusing the W5500's TX pointers while
the previous command is still in flight.

The first 256 two-byte block entries in section 4 are the y=64 layer. The
firmware writes `0x10, 0x00` for each of them, giving a 16x16 stone floor;
the remaining 7680 block bytes are air.

## Firmware limits

- Fixed display name `Player`; the client's Login Start name is skipped to
  keep the Login Success packet in flash.
- Inbound packet lengths are assumed to be one-byte VarInts. The handshake,
  login, and normal 1.8 play packets fit, but a very long hostname or chat
  message would not.
- One connection at a time.
- Placement is always stone and is limited to positions representable by the
  packed-byte adjustment (this demo supports x/z up to 255 and y up to
  4095; negative north/west targets are skipped).
- Block changes are client-authoritative until reconnect; the platform is
  regenerated from the chunk packet on each login. The client may keep
  showing a different creative block locally even though the server's Block
  Change is stone.
- A real 1.8.9 client is required. Modern clients can see the MOTD but cannot
  join.

## Testing

`tests/test_mc_void.py` runs the compiled firmware in the headless emulator
against a localhost 1.8.9 protocol client. `tests/w5500_sim.py` models the
W5500 SPI transactions, socket registers, 16 KB TX buffer, 2 KB RX buffer, and
a real localhost TCP connection.

```bash
python3 -m pytest tests/test_mc_void.py -q
```

The status/login/chunk/keepalive exchange has been run against the badge
hardware over Ethernet. The remaining check is a real vanilla 1.8.9 client,
plus confirming the W5500 buffer-size and timing assumptions on a scope/logic
analyzer if the link misbehaves.
