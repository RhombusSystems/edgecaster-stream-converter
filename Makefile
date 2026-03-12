.PHONY: dev dev-backend dev-frontend install build test lint clean

# Development
dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	@echo "Run 'make dev-backend' and 'make dev-frontend' in separate terminals"

# Build
build-frontend:
	cd frontend && npm install && npm run build

build: build-frontend

# Test
test:
	python -m pytest backend/tests/ -v

lint:
	ruff check backend/
	cd frontend && npx tsc --noEmit

# Install
install:
	sudo bash scripts/install.sh

uninstall:
	sudo bash scripts/uninstall.sh

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist frontend/node_modules
	rm -rf backend/*.egg-info dist build
