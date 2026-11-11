"""A small W5500 + TCP model for running the badge firmware in the emulator.

The model watches the badge's bit-banged SPI pins after every emulated
instruction, implements the subset of the W5500 register/socket interface the
Minecraft server uses, and connects socket 0 to a real localhost TCP socket so
tests can speak the Minecraft protocol to it.
"""

from __future__ import annotations

import socket
from typing import Optional

from badgec.emulator import Emulator


class W5500Model:
    def __init__(self, port: int = 25565, debug: bool = False) -> None:
        self.port = port
        self.debug = debug
        self.common = bytearray(0x40)
        self.regs = bytearray(0x30)
        self.tx_buf = bytearray(0x4000)
        self.rx_buf = bytearray(0x800)

        self.tx_size = 0x4000
        self.rx_size = 0x800
        self.tx_rd = 0
        self.tx_wr = 0
        self.rx_rd = 0
        self.rx_wr = 0
        self.status = 0x00

        self.common[0x2E] = 0x01  # PHY link up
        self.common[0x39] = 0x04  # VERSIONR

        self.listener: Optional[socket.socket] = None
        self.conn: Optional[socket.socket] = None
        try:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", port))
            listener.listen(1)
            listener.setblocking(False)
            self.listener = listener
        except OSError:
            self.listener = None

        # SPI transaction state.
        self.cs = True
        self.sclk = False
        self.header: list[int] = []
        self.bit_count = 0
        self.tx_byte = 0
        self.phase = "header"
        self.bsb = 0
        self.addr = 0
        self.write = False
        self.data_index = 0
        self.read_byte = 0

    # ------------------------------------------------------------------
    # W5500 register/socket model
    # ------------------------------------------------------------------

    def tx_free(self) -> int:
        used = (self.tx_wr - self.tx_rd) & 0x3FFF
        return self.tx_size - used

    def rx_rsr(self) -> int:
        return (self.rx_wr - self.rx_rd) & 0x7FF

    def socket_read(self, addr: int) -> int:
        if addr == 0x03:
            return self.status
        if addr == 0x20:
            return (self.tx_free() >> 8) & 0xFF
        if addr == 0x21:
            return self.tx_free() & 0xFF
        if addr == 0x24:
            return (self.tx_wr >> 8) & 0xFF
        if addr == 0x25:
            return self.tx_wr & 0xFF
        if addr == 0x26:
            return (self.rx_rsr() >> 8) & 0xFF
        if addr == 0x27:
            return self.rx_rsr() & 0xFF
        if addr == 0x28:
            return (self.rx_rd >> 8) & 0xFF
        if addr == 0x29:
            return self.rx_rd & 0xFF
        return self.regs[addr]

    def socket_write(self, addr: int, value: int) -> None:
        if addr == 0x01:
            self.command(value)
        elif addr == 0x1F:
            self.tx_size = value * 1024
        elif addr == 0x24:
            self.tx_wr = (self.tx_wr & 0x00FF) | (value << 8)
        elif addr == 0x25:
            self.tx_wr = (self.tx_wr & 0xFF00) | value
        elif addr == 0x28:
            self.rx_rd = (self.rx_rd & 0x00FF) | (value << 8)
        elif addr == 0x29:
            self.rx_rd = (self.rx_rd & 0xFF00) | value
        else:
            self.regs[addr] = value

    def command(self, value: int) -> None:
        if self.debug:
            print(f"CMD {value:#04x} status_before={self.status:#04x}")
        if value == 0x01:  # OPEN
            self.status = 0x13
            # The real W5500 can retain a warm-start TX pointer; start at a
            # deliberately nonzero value so the firmware must read Sn_TX_WR.
            self.tx_rd = 0x4000
            self.tx_wr = 0x4000
            self.rx_rd = 0
            self.rx_wr = 0
        elif value == 0x02:  # LISTEN
            self.status = 0x14
        elif value == 0x10:  # CLOSE
            self.close_connection()
            self.status = 0x00
            self.tx_rd = 0
            self.tx_wr = 0
            self.rx_rd = 0
            self.rx_wr = 0
        elif value == 0x20:  # SEND
            self.send()
        elif value == 0x40:  # RECV
            pass
        self.regs[0x01] = 0

    def close_connection(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except OSError:
                pass
            self.conn = None

    def send(self) -> None:
        if self.conn is None or self.status != 0x17:
            return
        used = (self.tx_wr - self.tx_rd) & 0x3FFF
        if used == 0:
            return
        data = bytes(
            self.tx_buf[(self.tx_rd + index) & 0x3FFF] for index in range(used)
        )
        if self.debug:
            print(f"SEND {len(data)} bytes status={self.status:#04x}")
        try:
            self.conn.sendall(data)
        except OSError:
            self.status = 0x1C
            self.close_connection()
            return
        self.tx_rd = self.tx_wr

    def tick(self) -> None:
        if self.listener is not None and self.status == 0x14 and self.conn is None:
            try:
                conn, _ = self.listener.accept()
            except BlockingIOError:
                conn = None
            except OSError:
                conn = None
            if conn is not None:
                conn.setblocking(False)
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.conn = conn
                self.status = 0x17
                self.tx_rd = 0
                self.tx_wr = 0
                self.rx_rd = 0
                self.rx_wr = 0

        if self.conn is None:
            return
        while True:
            try:
                data = self.conn.recv(2048)
            except BlockingIOError:
                break
            except OSError:
                self.status = 0x1C
                self.close_connection()
                return
            if self.debug:
                print(f"RX {len(data)} bytes")
            if not data:
                self.status = 0x1C
                self.close_connection()
                return
            for byte in data:
                self.rx_buf[self.rx_wr & 0x7FF] = byte
                self.rx_wr = (self.rx_wr + 1) & 0x7FF
            if self.rx_rsr() > self.rx_size:
                # The badge is not keeping up; drop the connection rather than
                # silently corrupting the stream.
                self.status = 0x1C
                self.close_connection()
                return

    # ------------------------------------------------------------------
    # SPI pin decoding
    # ------------------------------------------------------------------

    def read_data(self, bsb: int, addr: int) -> int:
        if bsb == 0:
            return self.common[addr & 0x3F]
        if bsb == 1:
            return self.socket_read(addr & 0x3F)
        if bsb == 2:
            return self.tx_buf[addr & 0x3FFF]
        if bsb == 3:
            value = self.rx_buf[addr & 0x7FF]
            if self.debug:
                print(f"RXREAD {addr & 0x7FF:#05x} -> {value:#04x}")
            return value
        return 0

    def write_data(self, bsb: int, addr: int, value: int) -> None:
        if bsb == 0:
            self.common[addr & 0x3F] = value
        elif bsb == 1:
            self.socket_write(addr & 0x3F, value)
        elif bsb == 2:
            self.tx_buf[addr & 0x3FFF] = value
        elif bsb == 3:
            self.rx_buf[addr & 0x7FF] = value

    def begin_transaction(self) -> None:
        self.header = []
        self.bit_count = 0
        self.tx_byte = 0
        self.phase = "header"
        self.bsb = 0
        self.addr = 0
        self.write = False
        self.data_index = 0
        self.read_byte = 0

    def on_sclk_rising(self, mosi: int, cpu: Emulator) -> None:
        if self.phase == "data" and not self.write:
            if self.bit_count == 0:
                self.read_byte = self.read_data(self.bsb, self.addr + self.data_index)
            miso = (self.read_byte >> (7 - self.bit_count)) & 1
        else:
            miso = 0
        cpu.ram[0x0B] = (cpu.ram[0x0B] & 0x0E) | miso

        self.tx_byte = ((self.tx_byte << 1) | mosi) & 0xFF
        self.bit_count += 1
        if self.bit_count != 8:
            return

        byte = self.tx_byte
        self.bit_count = 0
        self.tx_byte = 0

        if self.phase == "header":
            self.header.append(byte)
            if len(self.header) == 3:
                self.addr = (self.header[0] << 8) | self.header[1]
                control = self.header[2]
                self.bsb = control >> 3
                self.write = bool(control & 0x04)
                if self.debug:
                    print(f"SPI bsb={self.bsb} addr={self.addr:#06x} write={self.write}")
                self.phase = "data"
                self.data_index = 0
            return

        if self.write:
            self.write_data(self.bsb, self.addr + self.data_index, byte)
        self.data_index += 1

    def pins(self, before: int, after: int, cpu: Emulator) -> None:
        cs_before = bool(before & 0x02)
        cs_after = bool(after & 0x02)
        sclk_before = bool(before & 0x04)
        sclk_after = bool(after & 0x04)
        mosi = 1 if (after & 0x08) else 0

        if cs_before and not cs_after:
            self.begin_transaction()
        if not cs_after and not sclk_before and sclk_after:
            self.on_sclk_rising(mosi, cpu)
        if not cs_before and cs_after:
            self.phase = "idle"
        self.cs = cs_after
        self.sclk = sclk_after

    def close(self) -> None:
        self.close_connection()
        if self.listener is not None:
            try:
                self.listener.close()
            except OSError:
                pass
            self.listener = None


class W5500Emulator(Emulator):
    def __init__(self, model: W5500Model, tick_interval: int = 200) -> None:
        super().__init__()
        self.model = model
        self.tick_interval = tick_interval
        self.total_steps = 0
        self.out_before = 0

    def step(self) -> None:
        self.out_before = self.ram[0x0A]
        super().step()
        self.model.pins(self.out_before, self.ram[0x0A], self)
        self.total_steps += 1
        if self.total_steps % self.tick_interval == 0:
            self.model.tick()
