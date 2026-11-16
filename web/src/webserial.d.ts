export interface NiblickSerialOptions {
  baudRate: number;
  dataBits?: number;
  stopBits?: number;
  parity?: "none" | "even" | "odd";
  flowControl?: "none" | "hardware";
  bufferSize?: number;
}

export interface NiblickSerialPort {
  open(options: NiblickSerialOptions): Promise<void>;
  close(): Promise<void>;
  readonly writable: WritableStream<Uint8Array> | null;
}

export interface NiblickSerial {
  requestPort(): Promise<NiblickSerialPort>;
  getPorts(): Promise<NiblickSerialPort[]>;
}
