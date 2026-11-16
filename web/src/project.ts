import { strToU8, unzipSync, zipSync } from "fflate";

export const PROJECT_FORMAT = "niblick-project";
export const PROJECT_VERSION = 1;
export const PROJECT_MANIFEST = "niblick.json";
export const PROJECT_STORAGE_KEY = "niblick.project.v1";
export const PROJECT_MAX_FILES = 200;
export const PROJECT_MAX_FILE_BYTES = 1024 * 1024;
export const PROJECT_MAX_TOTAL_BYTES = 4 * 1024 * 1024;
export type ProjectLanguage = "niblick" | "voja4-asm";

export type ProjectManifest = {
  format: typeof PROJECT_FORMAT;
  version: number;
  name: string;
  entry: string;
};

export type ProjectSnapshot = {
  name: string;
  entry: string;
  active: string;
  files: Record<string, string>;
};

export const NEW_PROJECT_SOURCE = `fn main() {
    while (1) {
    }
}
`;

export const NEW_ASM_SOURCE = `; Import this module from a .nbl file:
;   import "path/to/module.asm";
;   extern fn void my_function();

; fn_my_function:
;     RET R0, 0
`;

export function languageForPath(path: string): ProjectLanguage {
  return path.toLowerCase().endsWith(".asm") ? "voja4-asm" : "niblick";
}

export function isSourcePath(path: string): boolean {
  return /\.(nbl|asm)$/i.test(path);
}

export function normalizeProjectPath(input: string): string {
  const path = input.trim().replace(/\\/g, "/");
  if (path.length === 0) {
    throw new Error("Enter a file name.");
  }
  if (path.startsWith("/") || /^[A-Za-z]:/.test(path)) {
    throw new Error("Use a project-relative path.");
  }
  if (path.includes("\0")) {
    throw new Error("The file name contains an invalid character.");
  }
  if (path.length > 160) {
    throw new Error("The file path is too long.");
  }
  const segments = path.split("/");
  for (const segment of segments) {
    if (segment.length === 0 || segment === "." || segment === "..") {
      throw new Error("Use a clean relative path without . or .. segments.");
    }
  }
  return path;
}

export function validateSourcePath(input: string): string {
  const path = normalizeProjectPath(input);
  if (path === PROJECT_MANIFEST || path.endsWith(`/${PROJECT_MANIFEST}`)) {
    throw new Error(`${PROJECT_MANIFEST} is reserved for the project manifest.`);
  }
  if (!isSourcePath(path)) {
    throw new Error("Use a .nbl or .asm file name.");
  }
  return path;
}

export function joinProjectPath(root: string, relative: string): string {
  return `${root.replace(/\/+$/, "")}/${relative}`;
}

export function relativeProjectPath(
  root: string,
  absolute: string,
): string | null {
  const prefix = `${root.replace(/\/+$/, "")}/`;
  return absolute.startsWith(prefix) ? absolute.slice(prefix.length) : null;
}

export function projectDownloadName(name: string): string {
  const base = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `${base || "niblick-project"}.zip`;
}

export function buildProjectZip(project: ProjectSnapshot): Uint8Array {
  const entry = validateSourcePath(project.entry);
  if (!(entry in project.files)) {
    throw new Error("The project entry file is missing.");
  }
  const manifest: ProjectManifest = {
    format: PROJECT_FORMAT,
    version: PROJECT_VERSION,
    name: project.name.trim() || "untitled",
    entry,
  };
  const archive: Record<string, Uint8Array> = {
    [PROJECT_MANIFEST]: strToU8(`${JSON.stringify(manifest, null, 2)}\n`),
  };
  for (const path of Object.keys(project.files).sort()) {
    const relative = validateSourcePath(path);
    if (relative === PROJECT_MANIFEST) {
      continue;
    }
    archive[relative] = strToU8(project.files[path]);
  }
  return zipSync(archive, { level: 6 });
}

function ignoredZipPath(path: string): boolean {
  return (
    path === ".DS_Store" ||
    path.endsWith("/.DS_Store") ||
    path.startsWith("__MACOSX/")
  );
}

function decodeZipText(data: Uint8Array): string {
  const text = new TextDecoder("utf-8", { fatal: true }).decode(data);
  if (text.includes("\0")) {
    throw new Error("The archive contains a binary file.");
  }
  return text.replace(/^\uFEFF/, "");
}

function commonZipRoot(paths: string[]): string | null {
  if (paths.length === 0) {
    return null;
  }
  const first = paths[0].split("/");
  if (first.length < 2) {
    return null;
  }
  const root = first[0];
  return paths.every((path) => path.startsWith(`${root}/`)) ? root : null;
}

function parseManifest(text: string): Partial<ProjectManifest> {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new Error(`${PROJECT_MANIFEST} is not valid JSON.`);
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${PROJECT_MANIFEST} must contain an object.`);
  }
  const record = value as Record<string, unknown>;
  if (
    record.format !== undefined &&
    record.format !== PROJECT_FORMAT
  ) {
    throw new Error("Unsupported project manifest format.");
  }
  if (
    record.version !== undefined &&
    (typeof record.version !== "number" || record.version > PROJECT_VERSION)
  ) {
    throw new Error("Unsupported project manifest version.");
  }
  return {
    format: PROJECT_FORMAT,
    version:
      typeof record.version === "number" ? record.version : PROJECT_VERSION,
    name: typeof record.name === "string" ? record.name : "",
    entry: typeof record.entry === "string" ? record.entry : "",
  };
}

export function readProjectZip(
  data: Uint8Array,
  fallbackName: string,
): ProjectSnapshot {
  let total = 0;
  let fileCount = 0;
  const archive = unzipSync(data, {
    filter: (file) => {
      if (file.name.endsWith("/")) {
        return false;
      }
      normalizeProjectPath(file.name);
      if (ignoredZipPath(file.name)) {
        return false;
      }
      fileCount += 1;
      if (fileCount > PROJECT_MAX_FILES) {
        throw new Error(`The archive has more than ${PROJECT_MAX_FILES} files.`);
      }
      if (file.originalSize > PROJECT_MAX_FILE_BYTES) {
        throw new Error(`${file.name} is larger than 1 MiB.`);
      }
      total += file.originalSize;
      if (total > PROJECT_MAX_TOTAL_BYTES) {
        throw new Error("The archive expands to more than 4 MiB.");
      }
      return true;
    },
  });

  const names = Object.keys(archive).map((name) =>
    normalizeProjectPath(name),
  );
  const root = commonZipRoot(names);
  const files: Record<string, string> = {};
  let manifestText: string | null = null;
  for (const [name, data] of Object.entries(archive)) {
    const full = normalizeProjectPath(name);
    const path = root === null ? full : full.slice(root.length + 1);
    if (path.length === 0) {
      continue;
    }
    if (path === PROJECT_MANIFEST) {
      manifestText = decodeZipText(data);
      continue;
    }
    if (!isSourcePath(path)) {
      continue;
    }
    const relative = validateSourcePath(path);
    if (relative in files) {
      throw new Error(`Duplicate project file: ${relative}`);
    }
    files[relative] = decodeZipText(data);
  }

  const manifest =
    manifestText === null ? null : parseManifest(manifestText);
  const entry = manifest?.entry
    ? validateSourcePath(manifest.entry)
    : inferEntry(files);
  if (!entry.toLowerCase().endsWith(".nbl")) {
    throw new Error("A project needs a .nbl entry file.");
  }
  if (!(entry in files)) {
    throw new Error(`The archive does not contain entry file ${entry}.`);
  }
  return {
    name: manifest?.name?.trim() || fallbackName || "untitled",
    entry,
    active: entry,
    files,
  };
}

function inferEntry(files: Record<string, string>): string {
  const sources = Object.keys(files).filter((path) =>
    path.toLowerCase().endsWith(".nbl"),
  );
  const main = sources.find(
    (path) => path === "main.nbl" || path.endsWith("/main.nbl"),
  );
  if (main !== undefined) {
    return main;
  }
  sources.sort((left, right) => {
    const leftRoot = left.includes("/") ? 1 : 0;
    const rightRoot = right.includes("/") ? 1 : 0;
    return leftRoot - rightRoot || left.localeCompare(right);
  });
  if (sources.length === 0) {
    throw new Error("A project needs at least one .nbl file.");
  }
  return sources[0];
}

export function saveProject(project: ProjectSnapshot): string | null {
  try {
    localStorage.setItem(
      PROJECT_STORAGE_KEY,
      JSON.stringify({ version: PROJECT_VERSION, ...project }),
    );
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : String(error);
  }
}

export function loadStoredProject(): ProjectSnapshot | null {
  let stored: string | null = null;
  try {
    stored = localStorage.getItem(PROJECT_STORAGE_KEY);
  } catch {
    return null;
  }
  if (stored === null) {
    return null;
  }
  try {
    const value = JSON.parse(stored) as Record<string, unknown>;
    if (value.version !== PROJECT_VERSION) {
      return null;
    }
    const name = typeof value.name === "string" ? value.name : "untitled";
    const entry =
      typeof value.entry === "string" ? validateSourcePath(value.entry) : "";
    const active =
      typeof value.active === "string" ? value.active : entry;
    if (
      typeof value.files !== "object" ||
      value.files === null ||
      Array.isArray(value.files)
    ) {
      return null;
    }
    const files: Record<string, string> = {};
    let total = 0;
    const entries = Object.entries(
      value.files as Record<string, unknown>,
    );
    if (entries.length > PROJECT_MAX_FILES) {
      return null;
    }
    for (const [key, text] of entries) {
      if (typeof text !== "string") {
        return null;
      }
      if (text.length > PROJECT_MAX_FILE_BYTES) {
        return null;
      }
      const path = validateSourcePath(key);
      total += text.length;
      if (total > PROJECT_MAX_TOTAL_BYTES) {
        return null;
      }
      files[path] = text;
    }
    if (entry === "" || !(entry in files)) {
      return null;
    }
    return {
      name,
      entry,
      active: active in files ? active : entry,
      files,
    };
  } catch {
    return null;
  }
}

export function clearStoredProject(): void {
  try {
    localStorage.removeItem(PROJECT_STORAGE_KEY);
  } catch {
    // Storage may be unavailable; nothing else to do.
  }
}
