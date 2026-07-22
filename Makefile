.PHONY: quality lint format types test dev-up dev-down prod-up prod-down

COMPOSE := docker compose
DEV_COMPOSE := -f docker-compose.yml -f docker-compose.dev.yml
PROD_COMPOSE := -f docker-compose.yml -f docker-compose.prod.yml

quality: lint format types test

lint:
	uv run ruff check src tests pyproject.toml

format:
	uv run ruff format --check src tests pyproject.toml

types:
	uv run ty check

test:
	uv run pytest

dev-up:
	$(COMPOSE) $(DEV_COMPOSE) up -d

dev-down:
	$(COMPOSE) $(DEV_COMPOSE) down

prod-up:
	$(COMPOSE) $(PROD_COMPOSE) up --build -d

prod-down:
	$(COMPOSE) $(PROD_COMPOSE) down
