# Releasing

## Before publishing

1. Check the assembler and emulator pins in `pyproject.toml`.
2. Check `[project.urls]` in `pyproject.toml`.
3. Set the VS Code Marketplace publisher in `editors/vscode/package.json`.
4. Build and test:

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -e ".[dev,lsp,fidelity,docs]"
   .venv/bin/python -m pytest
   .venv/bin/python -m build
   ```

5. Install the wheel in a fresh environment and run:

   ```bash
   python -m niblick examples/hello.nbl --run
   ```

6. Check the repository history for removed paths, credentials, and personal
   paths:

   ```bash
   git log --all --oneline
   git rev-list --objects --all | grep -E 'epaper_badge|photobooth|tritone|blue_noise|vendor/'
   git grep -I -n -E 'furrysalamander|/home/mike|password|token|secret' $(git rev-list --all) -- . ':!tests/test_upstream_emulator.py'
   ```

7. Check the font data license in `lib/font.nbl`.
8. Push `main` and verify the rendered README, documentation site, and
   dependency URLs.
