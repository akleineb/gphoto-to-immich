# Google Photos to Immich Migration
# Simple Makefile for migrating Google Photos to Immich

# Default values
IMMICH_URL ?= http://localhost:2283
TAKEOUT_PATH ?= examples/Takeout

# Colors for better readability
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

.PHONY: help install analyze run

help: ## Show available commands
	@echo "$(GREEN)Google Photos to Immich Migration$(NC)"
	@echo "=================================="
	@echo ""
	@echo "$(YELLOW)Available Commands:$(NC)"
	@echo "  install    - Install Python dependencies"
	@echo "  analyze    - Analyze the sample files"
	@echo "  run        - Start the migration"
	@echo ""
	@echo "$(YELLOW)Usage:$(NC)"
	@echo "  make install"
	@echo "  make analyze"
	@echo "  make run"
	@echo ""
	@echo "$(YELLOW)With custom values:$(NC)"
	@echo "  IMMICH_URL=\"http://192.168.1.100:2283\" make run"
	@echo "  TAKEOUT_PATH=\"/path/to/takeout\" make analyze"

install: ## Install Python dependencies
	@echo "$(GREEN)📦 Installing Python dependencies...$(NC)"
	python3 setup.py install
	@echo "$(GREEN)✅ Installation completed!$(NC)"

analyze: ## Analyze the sample files
	@echo "$(GREEN)📊 Analyzing sample files...$(NC)"
	@if [ -n "$$TAKEOUT_PATH" ]; then \
		echo "Using TAKEOUT_PATH: $$TAKEOUT_PATH"; \
		python3 test_migration.py --analyze --takeout-path "$$TAKEOUT_PATH"; \
	else \
		echo "Using default sample files..."; \
		python3 test_migration.py --analyze; \
	fi

run: ## Start the migration
	@echo "$(GREEN)🚀 Starting migration...$(NC)"
	@if [ -z "$$IMMICH_API_KEY" ]; then \
		echo "$(RED)❌ IMMICH_API_KEY is not set!$(NC)"; \
		echo "Use: IMMICH_API_KEY=\"your-api-key\" make run"; \
		exit 1; \
	fi
	@if [ -z "$$IMMICH_URL" ]; then \
		echo "$(RED)❌ IMMICH_URL is not set!$(NC)"; \
		echo "Use: IMMICH_URL=\"http://your-server:port\" make run"; \
		exit 1; \
	fi
	@if [ -z "$$TAKEOUT_PATH" ]; then \
		echo "$(RED)❌ TAKEOUT_PATH is not set!$(NC)"; \
		echo "Use: TAKEOUT_PATH=\"/path/to/takeout\" make run"; \
		exit 1; \
	fi
	python3 gphoto_to_immich.py --takeout-path "$$TAKEOUT_PATH" --immich-url "$$IMMICH_URL" --api-key "$$IMMICH_API_KEY"