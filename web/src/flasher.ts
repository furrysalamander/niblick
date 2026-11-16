import type {
  NiblickSerial,
  NiblickSerialPort,
} from "./webserial";

export type FlashOptions = {
  preDelayMs: number;
  chunkSize: number;
  chunkDelayMs: number;
  paddingBytes: number;
};

export const DEFAULT_FLASH_OPTIONS: FlashOptions = {
  preDelayMs: 1000,
  chunkSize: 64,
  chunkDelayMs: 5,
  paddingBytes: 1024,
};

function serial(): NiblickSerial | undefined {
  return (navigator as Navigator & { serial?: NiblickSerial }).serial;
}

export function serialSupported(): boolean {
  return serial() !== undefined;
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export class Flasher {
  private port: NiblickSerialPort | null = null;

  async connect(): Promise<void> {
    const api = serial();
    if (api === undefined) {
      throw new Error("WebSerial is not available in this browser");
    }
    this.port = await api.requestPort();
  }

  get connected(): boolean {
    return this.port !== null;
  }

  async flash(
    data: Uint8Array,
    options: FlashOptions,
    onProgress: (message: string) => void,
  ): Promise<void> {
    if (this.port === null) {
      await this.connect();
    }
    const port = this.port;
    if (port === null) {
      throw new Error("no serial port");
    }

    onProgress("opening serial port at 9600 8N1");
    await port.open({
      baudRate: 9600,
      dataBits: 8,
      stopBits: 1,
      parity: "none",
      flowControl: "none",
    });

    const writer = port.writable?.getWriter();
    if (writer === undefined) {
      await port.close();
      throw new Error("serial port is not writable");
    }

    try {
      onProgress(
        `put the badge in DIR mode and press LOAD; sending in ${options.preDelayMs} ms`,
      );
      await sleep(options.preDelayMs);

      let sent = 0;
      const chunkSize = Math.max(1, options.chunkSize);
      while (sent < data.length) {
        const chunk = data.slice(sent, sent + chunkSize);
        await writer.write(chunk);
        sent += chunk.length;
        if (sent === data.length || sent % (chunkSize * 8) === 0) {
          onProgress(`sent ${sent} / ${data.length} bytes`);
        }
        await sleep(Math.max(0, options.chunkDelayMs));
      }

      if (options.paddingBytes > 0) {
        await writer.write(new Uint8Array(options.paddingBytes));
        sent += options.paddingBytes;
        onProgress(`sent ${sent} bytes including padding`);
      }
      await writer.ready;
    } finally {
      writer.releaseLock();
      try {
        await port.close();
      } catch {
        // The port may already be closed by the adapter.
      }
      this.port = null;
    }
  }
}
