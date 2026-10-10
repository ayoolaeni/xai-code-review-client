# Explainable AI Code Review Assistant — common tasks.
# On Windows without `make`, use tasks.ps1 instead (same targets): .\tasks.ps1 test

PY ?= backend/.venv/bin/python
ifeq ($(OS),Windows_NT)
PY := backend/.venv/Scripts/python.exe
endif

.PHONY: install install-backend install-frontend install-eslint dev backend frontend migrate \
        lint format test test-all test-backend test-frontend e2e perf docker-build up down \
        benchmark-dry check-ground-truth

install: install-backend install-eslint install-frontend

install-backend:
	cd backend && python -m venv .venv && ../$(PY) -m pip install -e ".[dev]"

install-eslint:
	cd backend/app/static_analysis/eslint && npm install --omit=dev

install-frontend:
	cd frontend && npm install

migrate:
	cd backend && ../$(PY) -m alembic upgrade head

backend: migrate
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

# Starts backend and frontend together (Ctrl+C stops both).
dev: migrate
	( cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000 ) & \
	( cd frontend && npm run dev ) ; wait

lint:
	cd backend && ../$(PY) -m ruff check --config pyproject.toml app tests ../evaluation/scripts
	cd backend && ../$(PY) -m black --config pyproject.toml --check app tests ../evaluation/scripts
	cd frontend && npm run lint

format:
	cd backend && ../$(PY) -m ruff check --config pyproject.toml --fix app tests ../evaluation/scripts
	cd backend && ../$(PY) -m black --config pyproject.toml app tests ../evaluation/scripts
	cd frontend && npm run format

test-backend:
	cd backend && ../$(PY) -m pytest -m "not tools and not perf and not live_gemini" --cov=app --cov-report=term-missing:skip-covered

test-frontend:
	cd frontend && npm run test

test: lint test-backend test-frontend

test-all: lint
	cd backend && ../$(PY) -m pytest -m "not perf and not live_gemini"
	cd frontend && npm run test

e2e:
	docker compose up -d --build
	cd frontend && npx playwright test

perf:
	cd backend && ../$(PY) -m pytest -m perf tests/perf -s

docker-build:
	docker build -t xai-code-review .

up:
	docker compose up --build

down:
	docker compose down

check-ground-truth:
	$(PY) evaluation/scripts/check_ground_truth.py

benchmark-dry:
	LLM_PROVIDER=mock $(PY) evaluation/scripts/run_benchmark.py --conditions system baseline --runs 2 --out evaluation/results/dry-run
	$(PY) evaluation/scripts/score_benchmark.py --results evaluation/results/dry-run
