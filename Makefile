.PHONY: help setup run run-verbose venv install build up down restart logs status clean test

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

build-all: build build-transformer ## Build all Docker images
	@echo "$(GREEN)✓ All images built$(NC)"
	@echo "$(GREEN)✓ Using pre-built ollama/ollama:latest$(NC)"

up: ## Start Docker containers (Ollama + PostgreSQL + Flask)
	@echo "$(YELLOW)Starting all containers...$(NC)"
	@if [ ! -f ".env" ] && [ -f ".env.example" ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env from .env.example$(NC)"; \
	fi
	@$(DOCKER_COMPOSE) --profile $(PROFILE) up -d
	@echo "$(GREEN)✓ All containers started$(NC)"
	@echo ""
	@echo "Monitor setup progress with: make logs"
	@echo "Or: docker compose logs -f ollama-setup"
	@echo ""
	@echo "Services:"
	@echo "  - Ollama: http://localhost:11434"
	@echo "  - PostgreSQL: localhost:25432"
	@echo "  - Flask API: http://localhost:5000"

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

test: venv ## Run tests
	@echo "$(YELLOW)Running tests...$(NC)"
	@$(VENV_PYTHON) test_cli.py
	@echo "$(GREEN)✓ Tests completed$(NC)"

# Additional convenience targets
.PHONY: exec-ollama pull-model list-models build-postgres exec-postgres flask-logs

build-postgres: ## Build PostgreSQL + Flask image
	@echo "$(YELLOW)Building PostgreSQL + Flask image...$(NC)"
	@$(DOCKER_COMPOSE) build postgres
	@echo "$(GREEN)✓ PostgreSQL + Flask image built$(NC)"

exec-postgres: ## Execute psql in PostgreSQL container
	@$(DOCKER_COMPOSE) exec postgres su - postgres -c "psql -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-vuhitra}"

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
