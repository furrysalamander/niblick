

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

import type * as Monaco from "monaco-editor/editor/editor.api";

export type SemanticCompletion = (
  source: string,
  line: number,
  column: number,
) => Promise<Array<{ name: string; kind: string; detail: string }>>;

export function registerNiblick(
  monaco: typeof import("monaco-editor/editor/editor.api"),
  semantic?: SemanticCompletion,
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
    triggerCharacters: [".", '"'],
    provideCompletionItems: async (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };

      const snippets = [
        {
          label: "main",
          detail: "fn main() { ... }",
          insertText: "fn main() {\n\t$0\n}",
        },
        {
          label: "fn",
          detail: "function definition",
          insertText: "fn ${1:void} ${2:name}(${3}) {\n\t$0\n}",
        },
        {
          label: "if",
          detail: "if statement",
          insertText: "if (${1:condition}) {\n\t$0\n}",
        },
        {
          label: "while",
          detail: "while loop",
          insertText: "while (${1:condition}) {\n\t$0\n}",
        },
        {
          label: "for",
          detail: "for loop",
          insertText: "for (${1:i} = 0; ${1:i} < ${2:n}; ${1:i}++) {\n\t$0\n}",
        },
        {
          label: "import",
          detail: "import a library module",
          insertText: 'import "lib/${1:uart}.nbl";',
        },
        {
          label: "asm",
          detail: "inline assembly block",
          insertText: "asm {\n\t$0\n}",
        },
        {
          label: "struct",
          detail: "struct declaration",
          insertText: "struct ${1:Name} {\n\t${2:nibble} ${3:field};\n};",
        },
      ].map((snippet) => ({
        ...snippet,
        kind: monaco.languages.CompletionItemKind.Snippet,
        insertTextRules:
          monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
        range,
      }));

      const keywordSuggestions = KEYWORDS.map((label) => ({
        label,
        kind: monaco.languages.CompletionItemKind.Keyword,
        insertText: label,
        range,
      }));
      const typeSuggestions = TYPES.map((label) => ({
        label,
        kind: monaco.languages.CompletionItemKind.TypeParameter,
        insertText: label,
        range,
      }));

      let semanticSuggestions: Array<{
        label: string;
        kind: Monaco.languages.CompletionItemKind;
        detail: string;
        insertText: string;
        insertTextRules?: Monaco.languages.CompletionItemInsertTextRule;
        range: typeof range;
      }> = [];
      if (semantic !== undefined) {
        try {
          const items = await semantic(
            model.getValue(),
            position.lineNumber,
            position.column,
          );
          semanticSuggestions = items.map((item) => {
            const callable =
              item.kind === "function" ||
              item.kind === "builtin" ||
              item.kind === "runtime" ||
              item.kind === "asm_function";
            let kind = monaco.languages.CompletionItemKind.Text;
            if (callable) {
              kind = monaco.languages.CompletionItemKind.Function;
            } else if (item.kind === "constant") {
              kind = monaco.languages.CompletionItemKind.Constant;
            } else if (
              item.kind === "global" ||
              item.kind === "local" ||
              item.kind === "param"
            ) {
              kind = monaco.languages.CompletionItemKind.Variable;
            } else if (item.kind === "asm_label") {
              kind = monaco.languages.CompletionItemKind.Reference;
            }
            return {
              label: item.name,
              kind,
              detail: item.detail,
              insertText: callable ? `${item.name}($0)` : item.name,
              insertTextRules: callable
                ? monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet
                : undefined,
              range,
            };
          });
        } catch (error) {
          console.warn("Niblick completion provider failed", error);
          semanticSuggestions = [];
        }
      }

      const seen = new Set<string>();
      const suggestions = [
        ...semanticSuggestions,
        ...snippets,
        ...keywordSuggestions,
        ...typeSuggestions,
      ].filter((item) => {
        if (seen.has(item.label)) {
          return false;
        }
        seen.add(item.label);
        return true;
      });
      return { suggestions };
    },
  });
}
