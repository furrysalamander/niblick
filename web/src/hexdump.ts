function printable(byte: number): string {
  return byte >= 0x20 && byte <= 0x7e ? String.fromCharCode(byte) : ".";
}

export function formatHexdump(
  bytes: Uint8Array,
  bytesPerLine = 16,
): string {
  const width = Math.max(1, bytesPerLine);
  const lines: string[] = [];
  for (let offset = 0; offset < bytes.length; offset += width) {
    const row = bytes.slice(offset, offset + width);
    const hex: string[] = [];
    const ascii: string[] = [];
    for (const byte of row) {
      hex.push(byte.toString(16).padStart(2, "0"));
      ascii.push(printable(byte));
    }
    while (hex.length < width) {
      hex.push("  ");
      ascii.push(" ");
    }
    lines.push(
      `${offset.toString(16).padStart(8, "0")}: ${hex.join(" ")}  ${ascii.join("")}`,
    );
  }
  return lines.join("\n");
}
