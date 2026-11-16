PYTHON ?= python3
EXAMPLES := $(wildcard examples/*.nbl)

.PHONY: test compile examples clean

test:
	$(PYTHON) -m pytest

compile:
	$(PYTHON) -m niblick examples/hello.nbl

examples:
	@set -e; for f in $(EXAMPLES); do \
		echo "== $$f"; \
		$(PYTHON) -m niblick "$$f"; \
	done

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache build dist *.egg-info
	find examples -maxdepth 1 -name '*.asm' -delete
	rm -f examples/*.hex
