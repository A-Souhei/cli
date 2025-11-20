.PHONY: help setup run run-verbose venv install build up down restart logs status clean test
.PHONY: exec-ollama pull-model list-models build-postgres exec-postgres flask-logs update-schema migrate-session
.PHONY: build-redis build-all-services up-redis up-all redis-logs redis-cli redis-clear

# Default target
.DEFAULT_GOAL := help

# Variables
VENV_DIR := venv
PYTHON := python3
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
DOCKER_COMPOSE := docker compose
PROFILE := ollama

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m

help: ## Show this help message
	@echo "AI CLI - Makefile Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""

setup: ## Run complete setup (venv + dependencies + Docker)
	@echo "$(YELLOW)Running setup...$(NC)"
	@chmod +x setup.sh
	@./setup.sh

run: venv ## Run the AI CLI
	@echo "$(YELLOW)Starting AI CLI...$(NC)"
	@chmod +x start.sh
	@./start.sh

run-verbose: venv ## Run the AI CLI in verbose mode
	@echo "$(YELLOW)Starting AI CLI (verbose mode)...$(NC)"
	@chmod +x start.sh
	@./start.sh --verbose

venv: ## Create Python virtual environment
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "$(YELLOW)Creating virtual environment...$(NC)"; \
		$(PYTHON) -m venv $(VENV_DIR); \
		echo "$(GREEN)✓ Virtual environment created$(NC)"; \
	else \
		echo "$(GREEN)✓ Virtual environment already exists$(NC)"; \
	fi

install: venv ## Install Python dependencies
	@echo "$(YELLOW)Installing dependencies...$(NC)"
	@$(VENV_PIP) install --upgrade pip -q
	@$(VENV_PIP) install -r requirements.txt -q
	@touch $(VENV_DIR)/.requirements_installed
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

build: ## Build Docker images
	@echo "$(YELLOW)Building PostgreSQL Docker image...$(NC)"
	@docker build -f src/postgresql/Dockerfile -t cli-postgres:latest .
	@echo "$(GREEN)✓ PostgreSQL + Flask image built$(NC)"

build-transformer: ## Build transformer Docker image
	@echo "$(YELLOW)Building Transformer Docker image...$(NC)"
	@docker build -f src/transformer/Dockerfile -t cli-transformer:latest .
	@echo "$(GREEN)✓ Transformer image built$(NC)"

build-redis: ## Build Redis API image
	@echo "$(YELLOW)Building Redis API image...$(NC)"
	@$(DOCKER_COMPOSE) build redis-api
	@echo "$(GREEN)✓ Redis API image built$(NC)"

build-all: build build-transformer build-redis ## Build all Docker images
	@echo "$(GREEN)✓ All images built$(NC)"
	@echo "$(GREEN)✓ Using pre-built ollama/ollama:latest and redis:7-alpine$(NC)"

build-all-services: build build-transformer build-redis ## Build all service images (alias for build-all)
	@echo "$(GREEN)✓ All service images built$(NC)"

up: ## Start Docker containers (Ollama profile only)
	@echo "$(YELLOW)Starting Ollama containers...$(NC)"
	@if [ ! -f ".env" ] && [ -f ".env.example" ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env from .env.example$(NC)"; \
	fi
	@$(DOCKER_COMPOSE) --profile $(PROFILE) up -d
	@echo "$(GREEN)✓ Ollama containers started$(NC)"
	@echo ""
	@echo "Monitor setup progress with: make logs"
	@echo "Or: docker compose logs -f ollama-setup"
	@echo ""
	@echo "Services:"
	@echo "  - Ollama: http://localhost:11434"

up-redis: ## Start Redis services (Redis + Redis API + Transformer)
	@echo "$(YELLOW)Starting Redis services...$(NC)"
	@if [ ! -f ".env" ] && [ -f ".env.example" ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env from .env.example$(NC)"; \
	fi
	@$(DOCKER_COMPOSE) --profile app up -d redis redis-api transformer
	@echo "$(GREEN)✓ Redis services started$(NC)"
	@echo ""
	@echo "Services:"
	@echo "  - Redis: localhost:26379"
	@echo "  - Redis API: http://localhost:17000"
	@echo "  - Transformer: http://localhost:16050"

up-all: ## Start all Docker containers (Ollama + PostgreSQL + Redis + Transformer)
	@echo "$(YELLOW)Starting all containers...$(NC)"
	@if [ ! -f ".env" ] && [ -f ".env.example" ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env from .env.example$(NC)"; \
	fi
	@$(DOCKER_COMPOSE) --profile ollama --profile app up -d
	@echo "$(GREEN)✓ All containers started$(NC)"
	@echo ""
	@echo "Monitor setup progress with: make logs"
	@echo ""
	@echo "Services:"
	@echo "  - Ollama: http://localhost:11434"
	@echo "  - PostgreSQL: localhost:25432"
	@echo "  - Flask API: http://localhost:15000"
	@echo "  - Redis: localhost:26379"
	@echo "  - Redis API: http://localhost:17000"
	@echo "  - Transformer: http://localhost:16050"

down: ## Stop and remove Docker containers
	@echo "$(YELLOW)Stopping containers...$(NC)"
	@$(DOCKER_COMPOSE) --profile $(PROFILE) down
	@echo "$(GREEN)✓ Containers stopped$(NC)"

restart: down up ## Restart Docker containers

logs: ## Show Docker container logs
	@$(DOCKER_COMPOSE) logs -f

status: ## Show status of Docker containers
	@$(DOCKER_COMPOSE) ps

clean: ## Remove virtual environment and Docker volumes
	@echo "$(YELLOW)Cleaning up...$(NC)"
	@read -p "Remove virtual environment? (y/N) " -n 1 -r; \
	echo; \
	if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
		rm -rf $(VENV_DIR); \
		echo "$(GREEN)✓ Virtual environment removed$(NC)"; \
	fi
	@read -p "Remove Docker volumes (this will delete downloaded models)? (y/N) " -n 1 -r; \
	echo; \
	if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
		$(DOCKER_COMPOSE) down -v; \
		echo "$(GREEN)✓ Docker volumes removed$(NC)"; \
	fi

test: install ## Run tests
	@echo "$(YELLOW)Running tests...$(NC)"
	@$(VENV_PYTHON) test_cli.py
	@echo "$(GREEN)✓ Tests completed$(NC)"

# Additional convenience targets
.PHONY: build-postgres exec-postgres flask-logs update-schema migrate-session
.PHONY: exec-ollama pull-model list-models
.PHONY: redis-logs redis-cli redis-clear redis-info redis-api-health transformer-health

build-postgres: ## Build PostgreSQL + Flask image
	@echo "$(YELLOW)Building PostgreSQL + Flask image...$(NC)"
	@$(DOCKER_COMPOSE) build postgres
	@echo "$(GREEN)✓ PostgreSQL + Flask image built$(NC)"

exec-postgres: ## Execute psql in PostgreSQL container
	@$(DOCKER_COMPOSE) exec postgres su - postgres -c "psql -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-vuhitra}"

update-schema: ## Update PostgreSQL schema (add/modify tables)
	@echo "$(YELLOW)Updating PostgreSQL schema...$(NC)"
	@chmod +x src/postgresql/update-schema.sh
	@./src/postgresql/update-schema.sh
	@echo "$(GREEN)✓ Schema update complete$(NC)"

migrate-session: ## Apply session feature database migration
	@echo "$(YELLOW)Applying session migration...$(NC)"
	@chmod +x scripts/apply_session_migration.sh
	@./scripts/apply_session_migration.sh
	@echo "$(GREEN)✓ Session migration complete$(NC)"

flask-logs: ## Show Flask application logs
	@$(DOCKER_COMPOSE) exec postgres tail -f /var/log/flask.out.log

exec-ollama: ## Execute command in Ollama container (usage: make exec-ollama CMD="ollama list")
	@$(DOCKER_COMPOSE) exec ollama $(CMD)

pull-model: ## Pull a model (usage: make pull-model MODEL=llama2)
	@if [ -z "$(MODEL)" ]; then \
		echo "$(YELLOW)Usage: make pull-model MODEL=llama2$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Pulling model: $(MODEL)...$(NC)"
	@$(DOCKER_COMPOSE) exec ollama ollama pull $(MODEL)
	@echo "$(GREEN)✓ Model $(MODEL) pulled$(NC)"

list-models: ## List available models in Ollama container
	@$(DOCKER_COMPOSE) exec ollama ollama list

# Redis-specific targets
redis-logs: ## Show Redis API logs
	@$(DOCKER_COMPOSE) logs -f redis-api

redis-cli: ## Execute Redis CLI in Redis container
	@echo "$(YELLOW)Connecting to Redis CLI...$(NC)"
	@echo "$(GREEN)Tip: Use 'KEYS *' to list all keys, 'GET key' to get value$(NC)"
	@$(DOCKER_COMPOSE) exec redis redis-cli

redis-clear: ## Clear all Redis data (WARNING: Deletes all cached contexts)
	@echo "$(YELLOW)WARNING: This will delete ALL Redis data including RAG contexts!$(NC)"
	@read -p "Are you sure? (y/N) " -n 1 -r; \
	echo; \
	if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
		$(DOCKER_COMPOSE) exec redis redis-cli FLUSHALL; \
		echo "$(GREEN)✓ Redis data cleared$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

redis-info: ## Show Redis information and statistics
	@echo "$(YELLOW)Redis Server Information:$(NC)"
	@$(DOCKER_COMPOSE) exec redis redis-cli INFO server | grep -E "redis_version|uptime_in_seconds|used_memory_human"
	@echo ""
	@echo "$(YELLOW)Database Statistics:$(NC)"
	@$(DOCKER_COMPOSE) exec redis redis-cli INFO keyspace

redis-api-health: ## Check Redis API health
	@echo "$(YELLOW)Checking Redis API health...$(NC)"
	@curl -s http://localhost:17000/health | python3 -m json.tool || echo "$(RED)Redis API not responding$(NC)"

transformer-health: ## Check Transformer service health
	@echo "$(YELLOW)Checking Transformer service health...$(NC)"
	@curl -s http://localhost:16050/health | python3 -m json.tool || echo "$(RED)Transformer service not responding$(NC)"
