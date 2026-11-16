#!/usr/bin/env python3
"""Send a Niblick .hex file to a Supercon.6 badge over a 3.3 V UART.

Usage:
    python3 scripts/flash.py /dev/ttyUSB0 examples/hello.hex
    python3 scripts/flash.py /dev/ttyUSB0 examples/hello.hex --baud 9600

Put the badge into DIR mode and press LOAD before running this.  The badge
serial protocol is raw 9600 8N1 by default.  This script needs pyserial:

    python3 -m pip install pyserial
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    import serial
except ImportError:  # pragma: no cover - depends on the user's environment
    serial = None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="serial device, e.g. /dev/ttyUSB0")
    parser.add_argument("hexfile", help="assembled .hex file")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="seconds to wait after opening the port before sending",
    )
    args = parser.parse_args(argv)

    if serial is None:
        print("pyserial is required: python3 -m pip install pyserial", file=sys.stderr)
        return 1

    data = Path(args.hexfile).read_bytes()
    if len(data) < 10:
        print(f"{args.hexfile}: too short to be a badge .hex file", file=sys.stderr)
        return 1

    print(f"opening {args.port} at {args.baud} 8N1")
    with serial.Serial(args.port, args.baud, bytesize=8, parity="N", stopbits=1, timeout=1) as port:
        time.sleep(args.delay)
        port.write(data)
        port.flush()
        time.sleep(max(0.25, len(data) / (args.baud / 10.0)))
    print(f"sent {len(data)} bytes from {args.hexfile}")
    print("the badge should now be running the loaded program")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
