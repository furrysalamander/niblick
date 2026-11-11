# Releasing

This repository is currently local-only and uses the working name **BadgeC**.
The upstream assembler is consumed through a pinned git dependency on the
packaging branch of the fork.

## Before publishing

1. **Rebrand.** Update the package name, console-script names, README title,
   VS Code extension name/publisher, and any references to `badgec`.
2. **Pin the assembler.** The dependency in `pyproject.toml` currently points
   at:
   `furrysalamander/2022-Supercon6-Badge-Tools` at commit
   `c576ebd08d4916909c89497fba1e1158eb540685`, subdirectory `assembler`.
   If the packaging change lands upstream, switch the URL to the upstream
   repository and pin the merged commit or a release tag.
3. **Optional emulator extra.** The `fidelity` extra points at the same fork
   commit, subdirectory `emulator`. Update it alongside the assembler pin.
4. **Update URLs.** Add the final GitHub repository URL to `pyproject.toml`
   (`[project.urls]`) and any README links.
5. **Build and test from clean state.**
   ```sh
   python3 -m venv .venv
   .venv/bin/python -m pip install -e ".[dev,lsp,fidelity]"
   .venv/bin/python -m pytest
   .venv/bin/python -m build
   ```
6. **Install the wheel in a fresh venv** and run:
   ```sh
   python -m badgec examples/hello.badge --run
   ```
7. **Scan history** for removed paths, credentials, and personal paths:
   ```sh
   git log --all --oneline
   git rev-list --objects --all | grep -E 'epaper_badge|photobooth|tritone|blue_noise|vendor/|docs/upstream'
   git grep -I -n -E 'furrysalamander|/home/mike|password|token|secret' $(git rev-list --all) -- . ':!tests/test_upstream_emulator.py'
   ```
   (The `furrysalamander` match in the pinned dependency URL is expected; update
   it if the fork moves.)
8. Create the GitHub repository, push `main`, and review the rendered README
   and dependency URLs before making it public.
