# Documentation style

## Scope

Document interfaces and invariants owned by this repository:

- language syntax and semantics
- standard-library interfaces
- compiler CLI and diagnostics
- runtime ABI and target details needed by compiler or runtime authors
- emulator, debugger, VS Code extension, and web editor

Do not document:

- adapter-specific wiring or host setup
- badge firmware procedures
- upstream assembler usage, syntax, or examples
- upstream repository contents
- hardware safety advice

Link to the owning source instead.

## Writing rules

- Use present tense and third person.
- State facts, constraints, and failure behavior.
- Use one fact per sentence.
- Use a table for three or more parallel facts.
- Use code blocks for syntax, formats, commands, and protocol fields.
- Put the most specific noun first: "The compiler rejects...", not "It is
  important to note that...".
- Keep examples only when they disambiguate syntax or behavior.
- Use `must` for requirements and `may` for permission. Do not use `should`.
- Mark unverified values as `unverified` and cite the source, or remove them.
- Do not narrate implementation history, test status, or authoring process.

## Prohibited prose

Delete these forms:

| Form | Action |
|---|---|
| `Note that`, `It is worth noting`, `Keep in mind` | Delete |
| `simply`, `just`, `obviously`, `of course` | Delete |
| `robust`, `seamless`, `powerful`, `comprehensive` | Delete |
| `almost certainly`, `probably`, `likely`, `typically`, `in practice` | Replace with a verified fact or remove |
| `This is what makes...`, `The result is...` | Delete or state the fact |
| `not just X but Y` | State Y |
| `allows you to`, `lets you`, `you can` | Rewrite as a direct statement |
| `we`, `our`, `let's` | Delete or use the passive |
| `should` | Use `must`, `does`, or delete |
| em dash | Use a colon, semicolon, or a new sentence |
| bold emphasis | Use a table or a heading |

## Page template

```markdown
# Noun phrase

One sentence defining the page.

## Scope or syntax

Facts.

## Interfaces

| Call | Returns | Behavior |
|---|---|---|
| ... | ... | ... |

## Limits

- constraint
- failure mode
```

## Cross-references

Use Sphinx document links for internal pages:

```markdown
See {doc}`../language/types`.
```

Use plain Markdown links for external URLs. Do not duplicate content from a
linked page.

## Automated checks

`tools/check_docs.py` rejects prohibited prose outside code blocks. Blockquotes
are excluded and may contain editorial notes.

`tests/test_docs.py` checks links, duplicate headings, CLI coverage, intrinsic
coverage, and public library function coverage.

Run:

```bash
python3 tools/check_docs.py
python3 -m pytest tests/test_docs.py
```
