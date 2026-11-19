"""Sphinx configuration for the Niblick documentation."""

from __future__ import annotations

project = "Niblick"
copyright = "2026, Mike Abbott"
author = "Mike Abbott"
version = "1.0"
release = "1.0"

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_reredirects",
]

source_suffix = {".md": "markdown"}
master_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

myst_heading_anchors = 3
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
myst_url_schemes = ["http", "https", "mailto"]

nitpicky = True
nitpick_ignore = [
    ("py:class", "Emulator"),
]

html_theme = "sphinx_rtd_theme"
html_title = "Niblick"
html_baseurl = "https://furrysalamander.github.io/niblick/docs/"
html_show_sourcelink = False
html_static_path = ["_static"]
html_css_files = ["custom.css"]

html_theme_options = {
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "titles_only": False,
}

linkcheck_timeout = 10
linkcheck_ignore = [
    r"http://localhost:\d+",
    r"https://github\.com/furrysalamander/niblick/edit/.*",
]

redirects = {
    "asm-imports": "language/asm-modules.html",
    "compiler": "internals/compiler.html",
    "debugging": "toolchain/debugging.html",
    "drivers/w5500": "standard-library/drivers/w5500.html",
    "inline-asm": "language/inline-asm.html",
    "isa": "internals/isa.html",
    "keys": "standard-library/keys.html",
    "memory-map": "internals/memory-map.html",
    "minecraft": "examples/index.html",
    "pins": "standard-library/board.html",
    "runtime-abi": "internals/runtime-abi.html",
    "serial": "standard-library/uart.html",
    "stdlib": "standard-library/index.html",
    "structs": "language/structs.html",
    "testing": "project/testing.html",
    "toolchain": "toolchain/emulator.html",
    "types": "language/types.html",
    "upstream-errata": "internals/compiler.html",
    "vscode": "toolchain/vscode.html",
}
