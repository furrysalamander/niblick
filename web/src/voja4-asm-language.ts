const INSTRUCTIONS = [
  "ADD",
  "ADC",
  "SUB",
  "SBB",
  "OR",
  "AND",
  "XOR",
  "MOV",
  "CP",
  "INC",
  "DEC",
  "DSZ",
  "EXR",
  "BIT",
  "BSET",
  "BCLR",
  "BTG",
  "RRC",
  "RET",
  "SKIP",
  "JR",
];

const PSEUDO_OPS = ["GOTO", "GOSUB", "NOP", "CPL", "NEG", "LSR", "SL", "RLC"];

const DIRECTIVES = ["EQU", "ORG", "BYTE", "ASCII", "NIBBLE"];

const CONDITIONS = ["C", "NC", "Z", "NZ", "GTE", "LT", "EQ", "NE"];

const SFRS = [
  "OUT",
  "OUTB",
  "IN",
  "INB",
  "JSR",
  "PCL",
  "PCM",
  "PCH",
  "PAGE",
  "CLOCK",
  "SYNC",
  "WRFLAGS",
  "RDFLAGS",
  "SERCTRL",
  "SERLOW",
  "SERHIGH",
  "RECEIVED",
  "AUTOOFF",
  "KEYSTATUS",
  "KEYREG",
  "DIMMER",
  "RANDOM",
];

const KEYWORDS = [
  ...INSTRUCTIONS,
  ...PSEUDO_OPS,
  ...DIRECTIVES,
  ...CONDITIONS,
  ...SFRS,
  "LOW",
  "MID",
  "HIGH",
];

export function registerVoja4Asm(
  monaco: typeof import("monaco-editor/editor/editor.main"),
): void {
  monaco.languages.register({ id: "voja4-asm" });
  monaco.languages.setMonarchTokensProvider("voja4-asm", {
    defaultToken: "",
    keywords: KEYWORDS,
    tokenizer: {
      root: [
        [/[ \t\r\n]+/, ""],
        [/;.*$/, "comment"],
        [/^\s*(fn_[A-Za-z0-9_]+)(:)/, ["entity.name.function", "delimiter"]],
        [
          /^\s*(__nib_[A-Za-z0-9_]+)(:)/,
          ["entity.name.function.runtime", "delimiter"],
        ],
        [/^\s*(\.[A-Za-z0-9_]+)(:)/, ["entity.name.label", "delimiter"]],
        [/^\s*([A-Za-z_][A-Za-z0-9_]*)(:)/, ["entity.name.label", "delimiter"]],
        [/\$\{[^}]*\}/, "variable.parameter"],
        [/[A-Za-z_][A-Za-z0-9_]*/, {
          cases: {
            "@keywords": "keyword",
            "@default": "identifier",
          },
        }],
        [/0[xX][0-9a-fA-F_]+/, "number.hex"],
        [/0[bB][01_]+/, "number.binary"],
        [/\d+/, "number"],
        [/"([^"\\]|\\.)*"/, "string"],
        [/[,:]/, "delimiter"],
      ],
    },
  });

  monaco.languages.setLanguageConfiguration("voja4-asm", {
    comments: { lineComment: ";" },
    brackets: [["[", "]"]],
  });
}
