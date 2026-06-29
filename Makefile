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
	python -m personal_agent_os.main

cli:
	python -m personal_agent_os.main --channel cli

telegram:
	python -m personal_agent_os.main --channel telegram

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

logs:
	docker compose logs -f
