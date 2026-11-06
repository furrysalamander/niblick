#!/usr/bin/env python3
"""Read serial output from a Supercon.6 badge.

Usage:
    python3 scripts/monitor.py /dev/ttyUSB0
    python3 scripts/monitor.py /dev/ttyUSB0 --baud 9600 --seconds 10

Requires pyserial: python3 -m pip install pyserial
"""

from __future__ import annotations

import argparse
import sys
import time

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--seconds", type=float, default=0, help="0 means run until Ctrl-C")
    args = parser.parse_args(argv)

    if serial is None:
        print("pyserial is required: python3 -m pip install pyserial", file=sys.stderr)
        return 1

    start = time.monotonic()
    print(f"listening on {args.port} at {args.baud} 8N1 (Ctrl-C to stop)")
    try:
        with serial.Serial(args.port, args.baud, bytesize=8, parity="N", stopbits=1, timeout=0.2) as port:
            while True:
                data = port.read(256)
                if data:
                    text = "".join(chr(b) if 32 <= b < 127 or b in (10, 13) else "." for b in data)
                    print(f"{data.hex(' '):<48}  {text}")
                if args.seconds and time.monotonic() - start >= args.seconds:
                    break
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
