.PHONY: help build up down logs shell migrate makemigrations createsuperuser collectstatic test demo-data

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the Docker containers
	docker-compose build

up: ## Start the application
	docker-compose up -d

down: ## Stop the application
	docker-compose down

logs: ## View application logs
	docker-compose logs -f

shell: ## Access Django shell
	docker-compose run --rm web python manage.py shell

migrate: ## Run database migrations
	docker-compose run --rm web python manage.py makemigrations
	docker-compose run --rm web python manage.py migrate

makemigrations: ## Create new migrations
	docker-compose run --rm web python manage.py makemigrations

createsuperuser: ## Create a superuser
	docker-compose run --rm web python manage.py createsuperuser

collectstatic: ## Collect static files
	docker-compose run --rm web python manage.py collectstatic --noinput

test: ## Run tests
	docker-compose run --rm web python manage.py test

demo-data: ## Load demo data
	docker-compose run --rm web python manage.py setup_demo_data

prod-up: ## Start production environment
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-down: ## Stop production environment
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

clean: ## Clean up containers and volumes
	docker-compose down -v
	docker system prune -f