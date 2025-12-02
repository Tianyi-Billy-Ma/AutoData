# AutoData Makefile
# Common development tasks and shortcuts

.PHONY: help install install-dev test test-cov lint format type-check clean docs serve-docs
.DEFAULT_GOAL := help

# Python and tool versions
PYTHON := python3.10
UV := uv
PIP := pip

# Project directories
SRC_DIR := autodata
TEST_DIR := tests
DOCS_DIR := docs

# Help
help: ## Show this help message
	@echo "AutoData Development Commands"
	@echo "============================="
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Installation
install: ## Install the package in development mode
	$(UV) sync

install-dev: ## Install with all development dependencies
	$(UV) sync --group dev,test,docs

install-full: ## Install with all optional dependencies
	$(UV) sync --group dev,test,docs

# Testing
test: ## Run all tests
	$(UV) run pytest

test-cov: ## Run tests with coverage report
	$(UV) run pytest --cov=$(SRC_DIR) --cov-report=html --cov-report=term

test-fast: ## Run only fast tests (exclude slow ones)
	$(UV) run pytest -m "not slow"

test-unit: ## Run only unit tests
	$(UV) run pytest -m unit

test-integration: ## Run only integration tests
	$(UV) run pytest -m integration

test-crawler: ## Run crawler-related tests
	$(UV) run pytest -m crawler

test-agent: ## Run agent-related tests
	$(UV) run pytest -m agent

# Code Quality
lint: ## Run all linting tools
	$(UV) run ruff check .
	$(UV) run black --check .
	$(UV) run isort --check-only .

format: ## Format code with all tools
	$(UV) run ruff check . --fix
	$(UV) run black .
	$(UV) run isort .

type-check: ## Run type checking with mypy
	$(UV) run mypy $(SRC_DIR)

quality: format lint type-check ## Run all code quality checks

# Security
security: ## Run security checks
	$(UV) run safety check
	$(UV) run bandit -r $(SRC_DIR)

# Documentation
docs: ## Build documentation
	$(UV) run sphinx-build -b html $(DOCS_DIR) $(DOCS_DIR)/_build/html

docs-clean: ## Clean documentation build
	rm -rf $(DOCS_DIR)/_build

serve-docs: docs ## Build and serve documentation locally
	$(UV) run python -m http.server 8001 -d $(DOCS_DIR)/_build/html

# Development
dev-setup: install-dev ## Set up development environment
	$(UV) run pre-commit install
	@echo "Development environment setup complete!"

pre-commit: ## Run pre-commit hooks on all files
	$(UV) run pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	$(UV) run pre-commit autoupdate

# CLI
cli: ## Run the AutoData CLI
	$(UV) run autodata --help

cli-crawl: ## Run a sample crawl (example)
	$(UV) run autodata crawl -u https://example.com -s title:h1 -s content:p

cli-status: ## Check system status
	$(UV) run autodata status

cli-init: ## Initialize configuration
	$(UV) run autodata init

# Dependencies
deps-update: ## Update all dependencies
	$(UV) lock --upgrade

deps-outdated: ## Show outdated dependencies
	$(UV) lock --check

deps-tree: ## Show dependency tree
	$(UV) tree

# Environment
venv: ## Create virtual environment
	$(UV) venv
	$(UV) sync

venv-remove: ## Remove virtual environment
	$(UV) venv remove

# Cleaning
clean: ## Clean build artifacts and cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

clean-all: clean ## Clean everything including virtual environment
	$(UV) venv remove || true
	rm -rf .venv/

# Monitoring and Debugging
monitor: ## Show system monitoring info
	@echo "Python version: $(shell $(PYTHON) --version)"
	@echo "uv version: $(shell $(UV) --version)"
	@echo "Installed packages:"
	$(UV) pip list

debug: ## Show debug information
	@echo "Current directory: $(PWD)"
	@echo "Python executable: $(shell which $(PYTHON))"
	@echo "uv executable: $(shell which $(UV))"
	@echo "Source directory: $(SRC_DIR)"
	@echo "Test directory: $(TEST_DIR)"

# Docker (if applicable)
docker-build: ## Build Docker image
	docker build -t autodata:latest .

docker-run: ## Run Docker container
	docker run -it --rm autodata:latest

# Release
release-check: ## Check if ready for release
	@echo "Checking release readiness..."
	$(UV) run pytest --cov=$(SRC_DIR) --cov-fail-under=90
	$(UV) run ruff check .
	$(UV) run black --check .
	$(UV) run mypy $(SRC_DIR)
	@echo "Release checks passed!"

# Quick development workflow
dev: format test ## Quick development cycle: format and test

full-check: quality test-cov security ## Run full quality check suite

# Default development workflow
all: install-dev dev-setup quality test-cov ## Complete development setup and checks
