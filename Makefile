.PHONY: lint typecheck test test-cov run build clean install pre-commit

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

run:
	$(PYTHON) main.py

build:
	$(PYTHON) -m PyInstaller --noconfirm elixir.spec

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
