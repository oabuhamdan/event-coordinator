# Event Coordinator

A Django web application for coordinating events based on user availability with multi-channel notifications.

## Features

### For Organizations
- **Organization Registration & Profile Management**
- **Event Creation & Management**
- **Subscriber Management**
- **Event Analytics & Response Tracking**
- **Multi-channel Notifications** (Email, SMS, WhatsApp)
- **API Configuration** for external notification services

### For Users
- **User Registration & Profile Management**
- **Organization Discovery & Subscription**
- **Recurring Availability Setting** (flexible scheduling)
- **Event Notifications** based on preferences
- **Event Response System** (Yes/No/Maybe)
- **Smart Filtering** (all events vs. matching schedule)

### Technical Features
- **Production-ready Django application**
- **Docker & Docker Compose setup**
- **PostgreSQL database**
- **Redis for caching and Celery**
- **Celery for background tasks**
- **Bootstrap 5 responsive UI**
- **REST API endpoints**
- **Comprehensive admin interface**

## Quick Start

### Prerequisites
- Docker
- Docker Compose

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd event-coordinator
```

2. **Make the startup script executable**
```bash
chmod +x start.sh
```

3. **Run the startup script**
```bash
./start.sh
```

4. **Configure environment variables**
   - Copy `.env.example` to `.env`
   - Update the configuration values as needed
   - Restart the application: `docker-compose restart`

5. **Create a superuser (optional)**
```bash
docker-compose run --rm web python manage.py createsuperuser
```

### Manual Setup

If you prefer manual setup:

```bash
# Build containers
docker-compose build

# Start database and Redis
docker-compose up -d db redis

# Run migrations
docker-compose run --rm web python manage.py makemigrations
docker-compose run --rm web python manage.py migrate

# Start all services
docker-compose up -d
```

## Usage

### Access Points
- **Main Application**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin/
- **API Endpoints**: http://localhost:8000/api/

### User Workflow

1. **Register** as either a User or Organization
2. **Organizations**: Complete profile setup with notification preferences
3. **Users**: Browse and subscribe to organizations
4. **Set Availability**: Define recurring availability patterns
5. **Create Events** (Organizations) or **Respond to Events** (Users)
6. **Receive Notifications** based on preferences and availability

### Organization Setup

1. Register as an organization
2. Complete organization profile
3. Configure notification settings:
   - **Email**: SMTP configuration
   - **SMS/WhatsApp**: Twilio API credentials
4. Create events and manage subscribers

### User Availability

Users can set complex recurring availability patterns:
- **Weekly recurring**: "Every Wednesday 2-3 PM"
- **Monthly recurring**: "First Monday of each month 10-11 AM"
- **Multiple time slots**: "Wednesday 12-1 PM AND 2-3 PM"
- **Availability types**: Sure (Green) or Maybe (Yellow)

## API Configuration

### Email (SMTP)
Configure in organization profile or environment variables:
- SMTP Host, Port, Username, Password
- Supports Gmail, Outlook, custom SMTP servers

### SMS/WhatsApp (Twilio)
Required Twilio credentials:
- Account SID
- Auth Token
- Phone Number (for SMS)
- WhatsApp Number (for WhatsApp)

## Development

### Project Structure
```
event_coordinator/
├── accounts/          # User management
├── organizations/     # Organization management
├── events/           # Event management & availability
├── notifications/    # Notification system
├── static/          # Static files
├── templates/       # HTML templates
├── requirements.txt # Python dependencies
├── docker-compose.yml
└── Dockerfile
```

### Running Tests
```bash
docker-compose run --rm web python manage.py test
```

### Database Operations
```bash
# Make migrations
docker-compose run --rm web python manage.py makemigrations

# Apply migrations
docker-compose run --rm web python manage.py migrate

# Django shell
docker-compose run --rm web python manage.py shell
```

### Logs
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f web
docker-compose logs -f celery
```

## Production Deployment

### Environment Variables
Set these for production:
```bash
DEBUG=0
SECRET_KEY=your-very-long-random-secret-key
SECURE_SSL_REDIRECT=1
SECURE_HSTS_SECONDS=31536000
```

### SSL/HTTPS
- Configure reverse proxy (nginx/Apache)
- Update `ALLOWED_HOSTS` in settings
- Set `SECURE_*` settings appropriately

### Database
- Use managed PostgreSQL service
- Configure backup strategy
- Set connection pooling

### Monitoring
- Configure logging
- Set up health checks
- Monitor Celery workers

## Troubleshooting

### Common Issues

1. **Database Connection Issues**
   - Ensure PostgreSQL is running
   - Check database credentials
   - Verify network connectivity

2. **Celery Tasks Not Running**
   - Check Redis connection
   - Verify Celery worker is running
   - Check task logs

3. **Notifications Not Sending**
   - Verify API credentials
   - Check organization notification settings
   - Review notification logs in admin

4. **Static Files Not Loading**
   - Run `collectstatic` command
   - Check `STATIC_ROOT` settings
   - Verify file permissions

### Debug Commands
```bash
# Check service status
docker-compose ps

# View container logs
docker-compose logs web

# Access Django shell
docker-compose run --rm web python manage.py shell

# Check database connection
docker-compose run --rm web python manage.py dbshell
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the logs for error messages

## Security Considerations

- Change default secret key in production
- Use environment variables for sensitive data
- Enable SSL/HTTPS in production
- Regularly update dependencies
- Monitor for security vulnerabilities
- Use strong passwords for database and admin accounts