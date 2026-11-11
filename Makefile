PYTHON ?= python3
EXAMPLES := $(wildcard examples/*.badge)

.PHONY: test compile examples clean

test:
	$(PYTHON) -m pytest

compile:
	$(PYTHON) -m badgec examples/hello.badge

examples:
	@set -e; for f in $(EXAMPLES); do \
		echo "== $$f"; \
		$(PYTHON) -m badgec "$$f"; \
	done

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache build dist *.egg-info
	find examples -maxdepth 1 -name '*.asm' ! -name 'mc_void.asm' -delete
	rm -f examples/*.hex
