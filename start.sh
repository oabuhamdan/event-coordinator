#!/bin/bash

# Event Coordinator Application Startup Script

echo "Starting Event Coordinator Application..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please update the .env file with your configuration settings."
fi

# Build and start the application
echo "Building Docker containers..."
docker compose build

echo "Starting services..."
docker compose up -d db redis

echo "Waiting for database to be ready..."
sleep 10

echo "Running migrations..."
docker compose run --rm web python manage.py makemigrations
docker compose run --rm web python manage.py migrate

echo "Creating superuser (optional)..."
echo "You can create a superuser by running: docker-compose run --rm web python manage.py createsuperuser"

echo "Collecting static files..."
docker compose run --rm web python manage.py collectstatic --noinput

echo "Starting all services..."
docker compose up -d

echo "Application is now running!"
echo "Visit http://localhost:8000 to access the application"
echo "Admin panel: http://localhost:8000/admin/"

echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"