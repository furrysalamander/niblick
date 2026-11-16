export function colorClassFor(file: string, line: number): string {
  let value = 0;
  const key = `${file}:${line}`;
  for (let index = 0; index < key.length; index += 1) {
    value = (value * 31 + key.charCodeAt(index)) >>> 0;
  }
  return `asm-color-${value % 8}`;
}
