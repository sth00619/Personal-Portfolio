PYTHON ?= .venv/bin/python

.PHONY: install data run test clean

install:
	python3.11 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

data:
	PYTHONPATH=src $(PYTHON) -m wo24.pipeline --download-only

run:
	PYTHONPATH=src $(PYTHON) -m wo24.pipeline

test:
	$(PYTHON) -m pytest
