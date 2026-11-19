PYTHON ?= python3
DOCS_PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo $(PYTHON); fi)
EXAMPLES := $(wildcard examples/*.nbl)

.PHONY: test compile examples docs docs-serve clean

test:
	$(PYTHON) -m pytest

compile:
	$(PYTHON) -m niblick examples/hello.nbl

examples:
	@set -e; for f in $(EXAMPLES); do \
		echo "== $$f"; \
		$(PYTHON) -m niblick "$$f"; \
	done

docs:
	$(DOCS_PYTHON) -m sphinx -W --keep-going -b html docs docs/_build/html

docs-serve:
	$(DOCS_PYTHON) -m sphinx_autobuild docs docs/_build/html

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache build dist *.egg-info docs/_build
	find examples -maxdepth 1 -name '*.asm' -delete
	rm -f examples/*.hex
