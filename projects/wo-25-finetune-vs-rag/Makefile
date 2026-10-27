PYTHON ?= .venv/bin/python

.PHONY: install data convert tune evaluate score test

install:
	python3.11 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt

data:
	PYTHONPATH=src $(PYTHON) -m wo25.data

convert:
	PYTHONPATH=src $(PYTHON) -m wo25.model --convert

tune:
	PYTHONPATH=src $(PYTHON) -m wo25.train

evaluate:
	PYTHONPATH=src $(PYTHON) -m wo25.evaluate

score:
	PYTHONPATH=src $(PYTHON) -m wo25.score

test:
	$(PYTHON) -m pytest

