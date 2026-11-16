

const TYPES = [
  "nibble",
  "u4",
  "i4",
  "char",
  "u8",
  "byte",
  "uint8_t",
  "i8",
  "int8_t",
  "uint16_t",
  "u16",
  "i16",
  "int16_t",
  "short",
  "int",
  "uint32_t",
  "u32",
  "i32",
  "int32_t",
  "long",
  "uint64_t",
  "u64",
  "i64",
  "int64_t",
  "half",
  "f16",
  "float",
  "f32",
  "bool",
  "flashptr",
  "void",
];

const KEYWORDS = [
  "fn",
  "const",
  "if",
  "else",
  "while",
  "for",
  "return",
  "break",
  "continue",
  "import",
  "extern",
  "asm",
  "struct",
  "true",
  "false",
];

const UNSUPPORTED = [
  "switch",
  "do",
  "enum",
  "typedef",
  "sizeof",
  "static",
  "volatile",
  "goto",
];

const OPERATORS = [
  "<<=",
  ">>=",
  "+=",
  "-=",
  "*=",
  "/=",
  "%=",
  "&=",
  "|=",
  "^=",
  "++",
  "--",
  "<<",
  ">>",
  "<=",
  ">=",
  "==",
  "!=",
  "&&",
  "||",
  "+",
  "-",
  "*",
  "/",
  "%",
  "&",
  "|",
  "^",
  "~",
  "!",
  "=",
  "<",
  ">",
  "?",
  ":",
];

export function registerNiblick(
  monaco: typeof import("monaco-editor/editor/editor.api"),
): void {
  monaco.languages.register({ id: "niblick", extensions: [".nbl"] });

  monaco.languages.setMonarchTokensProvider("niblick", {
    defaultToken: "",
    types: TYPES,
    keywords: KEYWORDS,
    unsupported: UNSUPPORTED,
    operators: OPERATORS,
    symbols: /[=><!~?:&|+\-*/^%]+/,
    tokenizer: {
      root: [
        [/[a-zA-Z_]\w*/, {
          cases: {
            "@types": "type",
            "@keywords": "keyword",
            "@unsupported": "invalid",
            "@default": "identifier",
          },
        }],
        { include: "@whitespace" },
        [/[{}()[\]]/, "@brackets"],
        [/@symbols/, {
          cases: {
            "@operators": "operator",
            "@default": "",
          },
        }],
        [/\$\{[^}]*\}/, "variable.parameter"],
        [/\d+\.\d*([eE][\-+]?\d+)?/, "number.float"],
        [/\.\d+([eE][\-+]?\d+)?/, "number.float"],
        [/\d+[eE][\-+]?\d+/, "number.float"],
        [/0[xX][0-9a-fA-F_]+/, "number.hex"],
        [/0[bB][01_]+/, "number.binary"],
        [/0[oO][0-7_]+/, "number.octal"],
        [/\d[\d_]*/, "number"],
        [/"([^"\\]|\\.)*$/, "string.invalid"],
        [/"/, { token: "string.quote", bracket: "@open", next: "@string" }],
        [/'([^'\\]|\\.)*'/, "string"],
      ],
      comment: [
        [/[^/*]+/, "comment"],
        [/\*\//, "comment", "@pop"],
        [/[/*]/, "comment"],
      ],
      string: [
        [/[^\\"]+/, "string"],
        [/\\./, "string.escape"],
        [/"/, { token: "string.quote", bracket: "@close", next: "@pop" }],
      ],
      whitespace: [
        [/[ \t\r\n]+/, ""],
        [/\/\*/, "comment", "@comment"],
        [/\/\/.*$/, "comment"],
      ],
    },
  });

  monaco.languages.setLanguageConfiguration("niblick", {
    comments: { lineComment: "//", blockComment: ["/*", "*/"] },
    brackets: [
      ["{", "}"],
      ["[", "]"],
      ["(", ")"],
    ],
    autoClosingPairs: [
      { open: "{", close: "}" },
      { open: "[", close: "]" },
      { open: "(", close: ")" },
      { open: '"', close: '"' },
      { open: "'", close: "'" },
    ],
    surroundingPairs: [
      { open: "{", close: "}" },
      { open: "[", close: "]" },
      { open: "(", close: ")" },
      { open: '"', close: '"' },
      { open: "'", close: "'" },
    ],
  });

  monaco.languages.registerCompletionItemProvider("niblick", {
    provideCompletionItems: (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };
      const suggestions = [...KEYWORDS, ...TYPES].map((label) => ({
        label,
        kind: monaco.languages.CompletionItemKind.Keyword,
        insertText: label,
        range,
      }));
      return { suggestions };
    },
  });
}
