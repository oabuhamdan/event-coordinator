import dj_database_url

from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Database
DATABASES = {
    'default': dj_database_url.config(default='sqlite:///db.sqlite3')
}
# Email backend for development
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp-pulse.com'
EMAIL_PORT = 2525
EMAIL_USE_TLS = False
EMAIL_HOST_USER = 'osamaabuhamdan@yahoo.com'
EMAIL_HOST_PASSWORD = 'KrpZB39rPPGr'
DEFAULT_FROM_EMAIL = "no-reply@wird.app"

# Celery Configuration
CELERY_TASK_ALWAYS_EAGER = True  # Execute tasks synchronously in development
CELERY_TASK_EAGER_PROPAGATES = True