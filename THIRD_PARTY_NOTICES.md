# Third-party notices

BadgeC is licensed under the GNU General Public License, version 3. It depends
on the following third-party packages.

## supercon6-assembler

- Source: <https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools>
- Package location: `assembler/` in the source repository
- License: MIT
- Copyright: 2022 Mike Szczys

The assembler is installed as a Python dependency rather than vendored into
this repository. The packaged version includes two small fixes: unexpected
parser exceptions are reported with line information, and `BYTE` pseudo-ops
advance the symbol address by two words.

## supercon6-emulator (optional)

- Source: <https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools>
- Package location: `emulator/` in the source repository
- License: GNU General Public License, version 3
- Copyright: 2022 Adam Zeloof

This package is used only by the optional `fidelity` test extra. It is not a
runtime dependency of BadgeC.

## 5x8 font glyph data

- Source: `examples/Hackaday-hamlet/hamlet.asm` in the upstream
  [2022-Supercon6-Badge-Tools](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools)
  repository
- Author: Voja Antonic
- License: no explicit license was found in the upstream example
- Used by: `lib/font.badge`

The scroller algorithm is a new BadgeC implementation. The glyph table is
adapted from the upstream demo. Before a public release, confirm that
redistribution is acceptable or replace the table with a new or public-domain
5x8 font.

## Documentation

The upstream Supercon.6 manuals and tutorial are copyrighted reference material
and are not redistributed in this repository. Links point at the canonical
upstream copies.
