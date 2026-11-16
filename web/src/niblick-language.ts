

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

import type * as Monaco from "monaco-editor/editor/editor.main";

export type CompletionSymbol = {
  name: string;
  kind: string;
  detail: string;
};

export type DefinitionLocation = {
  file: string;
  line: number;
  column: number;
};

export type ReferenceLocation = DefinitionLocation & {
  length: number;
};

export type NiblickLanguageBridge = {
  complete: (
    source: string,
    line: number,
    column: number,
  ) => Promise<CompletionSymbol[]>;
  definition: (
    source: string,
    line: number,
    column: number,
  ) => Promise<DefinitionLocation | null>;
  hover: (
    source: string,
    line: number,
    column: number,
  ) => Promise<string | null>;
  references: (
    source: string,
    line: number,
    column: number,
  ) => Promise<ReferenceLocation[]>;
};

export function registerNiblick(
  monaco: typeof import("monaco-editor/editor/editor.main"),
  bridge?: NiblickLanguageBridge,
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
      if (bridge !== undefined) {
        try {
          const items = await bridge.complete(
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

  if (bridge === undefined) {
    return;
  }

  monaco.languages.registerDefinitionProvider("niblick", {
    provideDefinition: async (model, position) => {
      const target = await bridge.definition(
        model.getValue(),
        position.lineNumber,
        position.column,
      );
      if (target === null) {
        return null;
      }
      return {
        uri: monaco.Uri.file(target.file),
        range: new monaco.Range(
          target.line,
          target.column,
          target.line,
          target.column + 1,
        ),
      };
    },
  });

  monaco.languages.registerHoverProvider("niblick", {
    provideHover: async (model, position) => {
      const text = await bridge.hover(
        model.getValue(),
        position.lineNumber,
        position.column,
      );
      if (text === null || text.length === 0) {
        return null;
      }
      const word = model.getWordAtPosition(position);
      return {
        contents: [{ value: text }],
        range:
          word === null
            ? undefined
            : new monaco.Range(
                position.lineNumber,
                word.startColumn,
                position.lineNumber,
                word.endColumn,
              ),
      };
    },
  });

  monaco.languages.registerReferenceProvider("niblick", {
    provideReferences: async (model, position) => {
      const items = await bridge.references(
        model.getValue(),
        position.lineNumber,
        position.column,
      );
      return items.map((item) => ({
        uri: monaco.Uri.file(item.file),
        range: new monaco.Range(
          item.line,
          item.column,
          item.line,
          item.column + item.length,
        ),
      }));
    },
  });
}
