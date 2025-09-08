.PHONY: help install dev build test clean docker-up docker-down docker-logs db-migrate db-reset

# Default target
help:
	@echo "Plinto Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install all dependencies"
	@echo "  make clean         Clean all build artifacts"
	@echo ""
	@echo "Development:"
	@echo "  make dev           Start development servers"
	@echo "  make build         Build all packages"
	@echo "  make test          Run all tests"
	@echo "  make lint          Run linters"
	@echo "  make typecheck     Run type checking"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up     Start Docker services"
	@echo "  make docker-down   Stop Docker services"
	@echo "  make docker-logs   View Docker logs"
	@echo "  make docker-build  Build Docker images"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate    Run database migrations"
	@echo "  make db-reset      Reset database"
	@echo "  make db-seed       Seed database with test data"

# Install dependencies
install:
	npm install
	cd apps/api && pip install -r requirements.txt
	cd apps/api && pip install -r requirements-dev.txt

# Development
dev:
	npm run dev

# Build all packages
build:
	npm run build

# Run tests
test:
	npm run test
	cd apps/api && pytest

# Lint code
lint:
	npm run lint
	cd apps/api && ruff check .

# Type checking
typecheck:
	npm run typecheck
	cd apps/api && mypy .

# Clean build artifacts
clean:
	rm -rf node_modules
	rm -rf apps/*/node_modules
	rm -rf packages/*/node_modules
	rm -rf apps/*/.next
	rm -rf apps/*/dist
	rm -rf packages/*/dist
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Docker commands
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-build:
	docker-compose build

docker-restart:
	docker-compose restart

# Database commands
db-migrate:
	docker-compose exec api alembic upgrade head

db-reset:
	docker-compose exec api alembic downgrade base
	docker-compose exec api alembic upgrade head

db-seed:
	docker-compose exec api python -m scripts.seed_database

# Production build
build-prod:
	NODE_ENV=production npm run build
	cd apps/api && pip install -r requirements.txt --target ./dist

# Deploy to staging
deploy-staging:
	@echo "Deploying to staging..."
	railway up --environment staging

# Deploy to production
deploy-prod:
	@echo "Deploying to production..."
	@echo "Run: railway up --environment production"

# Run security scan
security-scan:
	npm audit
	cd apps/api && pip-audit

# Generate API documentation
docs-api:
	cd apps/api && python -m scripts.generate_openapi > ../../docs/openapi.json

# Start individual services
start-api:
	cd apps/api && uvicorn main:app --reload --host 0.0.0.0 --port 8000

start-admin:
	cd apps/admin && npm run dev

start-docs:
	cd apps/docs && npm run dev

# Environment setup
setup-env:
	cp .env.example .env
	cp apps/api/.env.example apps/api/.env
	cp apps/admin/.env.example apps/admin/.env
	@echo "Environment files created. Please update with your values."