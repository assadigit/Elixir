.PHONY: lint typecheck test test-cov eval eval-check run build clean install pre-commit

PYTHON := python3
PIP := pip

install:
	$(PIP) install -r requirements.txt -e ".[dev]"
	pre-commit install

lint:
	ruff check core/ utils/ ui_qt/ tests/
	ruff format --check core/ utils/ ui_qt/ tests/

lint-fix:
	ruff check --fix core/ utils/ ui_qt/ tests/
	ruff format core/ utils/ ui_qt/ tests/

typecheck:
	mypy core/ utils/ --config-file pyproject.toml

test:
	pytest -x -q

test-cov:
	pytest --cov=core --cov=utils --cov-report=term-missing

# Phase 4.2/4.3 (V0.17): deterministic quality scorecards over the golden
# chapters (ROUGE-L, faithfulness, hallucination-rate, coverage, length
# policy) — re-runs the pipeline per chapter with the deterministic mock LLM.
eval:
	$(PYTHON) scripts/eval_summary.py

# Regression gate: fails on quality regressions vs the committed baseline
# (tests/golden/eval_baseline.json). Intentional changes re-baseline via
# `python scripts/eval_summary.py --save-baseline` — see the script docstring.
eval-check:
	$(PYTHON) scripts/eval_summary.py --check --json eval_scorecards.json

run:
	$(PYTHON) main.py

build:
	$(PYTHON) -m PyInstaller --noconfirm elixir.spec

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
