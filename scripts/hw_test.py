#!/usr/bin/env python3
"""Run the Niblick hardware self-test over UART.

Usage:
    python3 scripts/hw_test.py /dev/ttyUSB0
    python3 scripts/hw_test.py /dev/ttyUSB0 --timeout 30

Load examples/hw_test.hex, put the badge in RUN mode, then run this script.
The badge waits for the single character 'R'; this script sends it and
collects the PASS/FAIL report.
"""

from __future__ import annotations

import argparse
import re
import sys
import time

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None

DONE_RE = re.compile(r"DONE pass=([0-9A-Fa-f]{2}) fail=([0-9A-Fa-f]{2})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="serial device, e.g. /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--command-hex",
        default="01",
        help="single command byte in hex (default: 01)",
    )
    args = parser.parse_args(argv)

    if serial is None:
        print("pyserial is required: python3 -m pip install pyserial", file=sys.stderr)
        return 2

    try:
        command_int = int(args.command_hex, 16)
    except ValueError:
        print("--command-hex must be a hex byte, e.g. 01", file=sys.stderr)
        return 2
    if not 0 <= command_int <= 0xFF:
        print("--command-hex must be in 00..ff", file=sys.stderr)
        return 2
    command = bytes([command_int])

    with serial.Serial(
        args.port,
        args.baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=0.1,
    ) as port:
        time.sleep(0.3)
        port.reset_input_buffer()
        print(f"sending {command!r} to {args.port}")
        port.write(command)
        port.flush()

        data = bytearray()
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            chunk = port.read(256)
            if chunk:
                data.extend(chunk)
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
                if b"DONE " in data:
                    # Drain anything already queued after the summary.
                    time.sleep(0.2)
                    extra = port.read(port.in_waiting or 0)
                    if extra:
                        data.extend(extra)
                        sys.stdout.buffer.write(extra)
                        sys.stdout.buffer.flush()
                    break

    text = data.decode("ascii", errors="replace")
    match = DONE_RE.search(text)
    if not match:
        print("\nNO DONE line received; hardware test did not complete", file=sys.stderr)
        return 1

    passed = int(match.group(1), 16)
    failed = int(match.group(2), 16)
    print(f"\nSummary: {passed} passed, {failed} failed")
    return 0 if failed == 0 and passed > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
