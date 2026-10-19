# Shortcuts for the usual tasks. Run from the project root.
#   make setup   create .venv and install the pinned requirements
#   make data    download the raw files (cached) and rebuild data/processed
#   make run     start the app
#   make check   build every chart outside Streamlit (smoke test)

ifeq ($(OS),Windows_NT)
  PYTHON ?= python
  VENV_PY := .venv/Scripts/python.exe
else
  PYTHON ?= python3
  VENV_PY := .venv/bin/python
endif

.PHONY: setup data run check

setup:
	$(PYTHON) -m venv .venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -r requirements.txt

data:
	$(VENV_PY) scripts/build_data.py --download --prepare --quality

run:
	$(VENV_PY) -m streamlit run app.py

check:
	$(VENV_PY) scripts/check_charts.py
