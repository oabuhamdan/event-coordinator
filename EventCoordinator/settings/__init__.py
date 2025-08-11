import os
from decouple import config

# Determine which settings to use based on environment
environment = config('DJANGO_ENVIRONMENT', default='development')

if environment == 'production':
    print("Loading production settings...")
    from .prod import *
else:
    print("Loading development settings...")
    from .dev import *

print(f"Django environment: {environment}")
print(f"Debug mode: {DEBUG}")