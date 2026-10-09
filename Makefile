PYTHON ?= .venv/bin/python

.PHONY: install dev-backend dev-frontend test test-backend test-frontend test-e2e lint build check docker-up docker-down

install:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r backend/requirements-dev.txt
	npm --prefix frontend ci
	npm --prefix gc-worker ci

dev-backend:
	$(PYTHON) -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

dev-frontend:
	npm --prefix frontend run dev

test: test-backend test-frontend test-gc

test-backend:
	$(PYTHON) -m pytest -q

test-frontend:
	npm --prefix frontend test

test-gc:
	npm --prefix gc-worker test

test-e2e:
	npm --prefix frontend run test:e2e

lint:
	$(PYTHON) -m ruff check backend
	$(PYTHON) -m ruff format --check backend
	npm --prefix frontend run format:check
	npm --prefix frontend run lint

build:
	npm --prefix frontend run typecheck
	npm --prefix frontend run build

check: lint test build

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
