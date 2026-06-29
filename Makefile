.PHONY: install test lint fmt check run cli telegram docker-build docker-up docker-down

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

fmt:
	ruff format src/ tests/

check: lint test

run:
	python -m operation_drake.main

cli:
	python -m operation_drake.main --channel cli

telegram:
	python -m operation_drake.main --channel telegram

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

logs:
	docker compose logs -f
