"""End-to-end protocol test for examples/mc_void.badge.

A localhost Minecraft 1.8.9 client talks to the badge firmware running in the
headless emulator through a small W5500/TCP model.
"""

from __future__ import annotations

import socket
import struct
import threading
import time
from pathlib import Path

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.loader import load_program

from w5500_sim import W5500Emulator, W5500Model

ROOT = Path(__file__).resolve().parent.parent
PORT = 25565
HOST = "127.0.0.1"


def varint(value: int) -> bytes:
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def read_varint_bytes(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return value, offset
        shift += 7
        if shift > 21:
            raise ValueError("oversized VarInt")


def recv_exact(sock: socket.socket, count: int) -> bytes:
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise ConnectionError("peer closed")
        data.extend(chunk)
    return bytes(data)


def recv_varint(sock: socket.socket) -> int:
    value = 0
    shift = 0
    while True:
        byte = recv_exact(sock, 1)[0]
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return value
        shift += 7
        if shift > 21:
            raise ValueError("oversized VarInt")


def send_packet(sock: socket.socket, body: bytes) -> None:
    sock.sendall(varint(len(body)) + body)


def recv_packet(sock: socket.socket) -> tuple[int, bytes]:
    length = recv_varint(sock)
    body = recv_exact(sock, length)
    packet_id, offset = read_varint_bytes(body, 0)
    return packet_id, body[offset:]


def handshake(sock: socket.socket, next_state: int) -> None:
    address = HOST.encode("utf-8")
    body = (
        b"\x00"
        + varint(47)
        + varint(len(address))
        + address
        + struct.pack(">H", PORT)
        + varint(next_state)
    )
    send_packet(sock, body)


def connect_with_retry(timeout: float = 5.0) -> socket.socket:
    deadline = time.time() + timeout
    while True:
        try:
            sock = socket.create_connection((HOST, PORT), timeout=1.0)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(10.0)
            return sock
        except OSError:
            if time.time() > deadline:
                raise
            time.sleep(0.05)




def pack_pos(x: int, y: int, z: int) -> bytes:
    value = ((x & 0x3FFFFFF) << 38) | ((y & 0xFFF) << 26) | (z & 0x3FFFFFF)
    return struct.pack(">Q", value)


def expect_block_change(sock: socket.socket, position: bytes, state: int) -> None:
    while True:
        packet_id, payload = recv_packet(sock)
        if packet_id == 0x23:
            assert payload[:8] == position
            block_state, _ = read_varint_bytes(payload, 8)
            assert block_state == state
            return
        if packet_id == 0x00:
            keepalive_id, _ = read_varint_bytes(payload, 0)
            send_packet(sock, b"\x00" + varint(keepalive_id))
        # Ignore other play packets.

def status_test() -> None:
    with connect_with_retry() as sock:
        handshake(sock, 1)
        send_packet(sock, b"\x00")  # status request

        packet_id, payload = recv_packet(sock)
        assert packet_id == 0x00
        json_len, offset = read_varint_bytes(payload, 0)
        status = payload[offset:offset + json_len].decode("utf-8")
        assert "1.8.9" in status
        assert "Voja4" in status

        payload_value = 0x1122334455667788
        send_packet(sock, b"\x01" + struct.pack(">q", payload_value))
        packet_id, pong = recv_packet(sock)
        assert packet_id == 0x01
        assert struct.unpack(">q", pong)[0] == payload_value


def login_test() -> None:
    with connect_with_retry() as sock:
        handshake(sock, 2)
        name = b"TestPlayer"
        send_packet(sock, b"\x00" + varint(len(name)) + name)

        packet_id, payload = recv_packet(sock)
        assert packet_id == 0x02, f"expected Login Success, got {packet_id:#x}"
        uuid_len, offset = read_varint_bytes(payload, 0)
        offset += uuid_len
        name_len, offset = read_varint_bytes(payload, offset)
        login_name = payload[offset:offset + name_len]
        assert login_name == b"Player"

        expected = [0x01, 0x21, 0x08]
        packets = []
        for expected_id in expected:
            packet_id, payload = recv_packet(sock)
            assert packet_id == expected_id, (
                f"expected packet {expected_id:#x}, got {packet_id:#x}"
            )
            packets.append(payload)

        join, chunk, position = packets
        assert len(join) == 14
        assert len(position) == 33

        chunk_x, chunk_z = struct.unpack(">ii", chunk[:8])
        ground_up = chunk[8]
        mask = struct.unpack(">H", chunk[9:11])[0]
        data_len, offset = read_varint_bytes(chunk, 11)
        data = chunk[offset:offset + data_len]

        assert (chunk_x, chunk_z) == (0, 0)
        assert ground_up == 1
        assert mask == 0x0010
        assert data_len == 12544
        assert len(data) == 12544
        assert data[:512] == b"\x10\x00" * 256
        assert data[512:8192] == b"\x00" * 7680
        assert data[8192:10240] == b"\xFF" * 2048
        assert data[10240:12288] == b"\xFF" * 2048
        assert data[12288:] == b"\x7F" * 256

        # Exercise the play-state drain path with small client packets.
        send_packet(sock, b"\x15" + varint(5) + b"en_US" + b"\x08\x00\x01\x7F")
        send_packet(
            sock,
            b"\x04"
            + struct.pack(">ddd", 0.5, 65.0, 0.5)
            + b"\x00",
        )

        # The server sends a keepalive from the play loop; echo it back.
        packet_id, payload = recv_packet(sock)
        assert packet_id == 0x00, f"expected keepalive, got {packet_id:#x}"
        keepalive_id, _ = read_varint_bytes(payload, 0)
        send_packet(sock, b"\x00" + varint(keepalive_id))
        time.sleep(0.2)

        # Break one platform block, then place stone on all six faces of a
        # central platform block.
        center = pack_pos(4, 64, 4)
        send_packet(sock, b"\x07\x02" + center + b"\x01")
        expect_block_change(sock, center, 0)

        faces = [
            (0, pack_pos(4, 63, 4)),
            (1, pack_pos(4, 65, 4)),
            (2, pack_pos(4, 64, 3)),
            (3, pack_pos(4, 64, 5)),
            (4, pack_pos(3, 64, 4)),
            (5, pack_pos(5, 64, 4)),
        ]
        for face, target in faces:
            body = b"\x08" + center + bytes([face]) + b"\xff\xff" + b"\x00\x00\x00"
            send_packet(sock, body)
            expect_block_change(sock, target, 0x10)


def test_mc_void_status_and_login(tmp_path: Path) -> None:
    source = ROOT / "examples" / "mc_void.badge"
    compiler = Compiler(load_program(source), str(source))
    asm = compiler.compile()
    asm_path = tmp_path / "mc_void.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / "mc_void.hex"
    assemble_file(asm_path, hex_path)

    model = W5500Model(port=PORT)
    if model.listener is None:
        model.close()
        import pytest

        pytest.skip("port 25565 is unavailable")

    errors: list[tuple[str, BaseException]] = []
    done = threading.Event()

    def client() -> None:
        stage = "status"
        try:
            status_test()
            time.sleep(0.2)
            stage = "login"
            login_test()
        except BaseException as error:  # noqa: BLE001 - surfaced by the test
            errors.append((stage, error))
        finally:
            done.set()

    thread = threading.Thread(target=client, daemon=True)
    thread.start()

    cpu = W5500Emulator(model)
    cpu.load_hex(hex_path)
    deadline = time.monotonic() + 90.0
    try:
        while not done.is_set() and time.monotonic() < deadline:
            for _ in range(1000):
                cpu.step()
                if done.is_set():
                    break
            time.sleep(0)
    finally:
        model.close()
        thread.join(timeout=5)

    assert not thread.is_alive(), "client thread did not finish"
    assert not errors, (errors, f"after {cpu.total_steps} steps")
