PYTHON ?= python3

.PHONY: test validate index unittest

test: validate unittest

validate:
	$(PYTHON) scripts/validate_personas.py --check-index

index:
	$(PYTHON) scripts/build_index.py --write

unittest:
	$(PYTHON) -m unittest discover -s tests -v
