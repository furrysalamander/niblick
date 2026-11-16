# Releasing

## Before publishing

1. **Assembler pin.** The dependency in `pyproject.toml` points at
   `furrysalamander/2022-Supercon6-Badge-Tools` commit
   `c576ebd08d4916909c89497fba1e1158eb540685`, subdirectory `assembler`.
   That commit is on the fork's `packaging/pyproject` branch. The fork also
   carries two focused branches:
   - `fix/assembler-reporting` — assembler fixes based on upstream `main`
   - `packaging/pyproject-only` — packaging metadata based on upstream `main`

   If the packaging change lands upstream, replace the URL with the upstream
   repository and pin the merged commit or release tag.
2. **Emulator extra.** The `fidelity` extra points at the same fork commit,
   subdirectory `emulator`. Update it with the assembler pin.
3. **URLs.** Add the final repository URL to `pyproject.toml` under
   `[project.urls]`, and update links that depend on it.
4. **Publisher.** Create the VS Code Marketplace publisher and set the
   `publisher` field in `editors/vscode/package.json`.
5. **Clean build and test.**
   ```sh
   python3 -m venv .venv
   .venv/bin/python -m pip install -e ".[dev,lsp,fidelity]"
   .venv/bin/python -m pytest
   .venv/bin/python -m build
   ```
6. **Fresh wheel install.** Install the wheel in a new virtual environment and
   run:
   ```sh
   python -m niblick examples/hello.nbl --run
   ```
7. **History scan.** Check for removed paths, credentials, and personal paths:
   ```sh
   git log --all --oneline
   git rev-list --objects --all | grep -E 'epaper_badge|photobooth|tritone|blue_noise|vendor/|docs/upstream'
   git grep -I -n -E 'furrysalamander|/home/mike|password|token|secret' $(git rev-list --all) -- . ':!tests/test_upstream_emulator.py'
   ```
   The `furrysalamander` match in the pinned dependency URL is expected.
8. **Font data.** `lib/font.nbl` contains 5x8 glyph data adapted from the
   upstream Hamlet demo by Voja Antonic. The upstream example has no explicit
   license. Confirm redistribution permission or replace the glyph table with
   a new 5x8 font. The scroller implementation is original.
9. **Repository.** Create the GitHub repository, push `main`, and verify the
   rendered README and dependency URLs.
