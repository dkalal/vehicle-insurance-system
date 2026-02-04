# Technology Stack

## Programming Languages
- **Python 3.12+**: Primary backend language
- **JavaScript**: Frontend interactivity with Alpine.js
- **HTML5**: Semantic markup with accessibility compliance
- **CSS3**: Styling via Tailwind CSS utility framework
- **SQL**: PostgreSQL database queries and migrations

## Backend Framework
- **Django 5.0.1**: Modern Python web framework
- **Django REST Framework 3.14.0**: API development
- **Django Environ 0.11.2**: Environment variable management
- **Django Filter 23.5**: Advanced filtering and search

## Database & Caching
- **PostgreSQL**: Primary database with advanced features
- **psycopg[binary] 3.2-3.4**: PostgreSQL adapter with binary libpq
- **Redis 5.0.1**: Caching and message broker
- **Django Redis 5.4.0**: Django-Redis integration

## Background Processing
- **Celery 5.3.6**: Asynchronous task queue
- **Redis**: Message broker for Celery
- **Periodic Tasks**: Scheduled notifications and cleanup

## Security & Compliance
- **Django CORS Headers 4.3.1**: Cross-origin resource sharing
- **Django CSP 3.7**: Content Security Policy
- **Django Simple History 3.4.0**: Model history tracking
- **Django Auditlog 2.3.0**: Audit trail logging

## Reporting & Analytics
- **ReportLab 4.0.9**: PDF report generation
- **OpenPyXL 3.1.2**: Excel file generation
- **Custom reporting engine**: Built-in analytics

## Monitoring & Performance
- **psutil 5.9.8**: System monitoring
- **python-json-logger 2.0.7**: Structured logging
- **Sentry SDK 1.40.6**: Error tracking and performance monitoring
- **Django Debug Toolbar 4.2.0**: Development debugging

## API Documentation
- **DRF Spectacular 0.27.1**: OpenAPI/Swagger documentation
- **Auto-generated docs**: Interactive API explorer

## Production Server
- **Gunicorn 21.2.0**: WSGI HTTP server
- **WhiteNoise 6.6.0**: Static file serving with compression
- **Nginx**: Reverse proxy and load balancing (via Docker)

## Frontend Technologies
- **Tailwind CSS**: Utility-first CSS framework
- **Alpine.js**: Lightweight JavaScript framework
- **Responsive Design**: Mobile-first approach
- **WCAG 2.1 AA**: Accessibility compliance

## Development Tools
- **IPython 8.20.0**: Enhanced Python shell
- **Black 23.12.1**: Code formatting
- **isort 5.13.2**: Import sorting
- **Flake8 7.0.0**: Code linting
- **MyPy 1.8.0**: Static type checking
- **Django Stubs 4.2.7**: Type hints for Django

## Testing Framework
- **pytest 7.4.4**: Testing framework
- **pytest-django 4.8.0**: Django integration
- **pytest-cov 4.1.0**: Coverage reporting
- **Factory Boy 3.3.0**: Test data generation

## Containerization
- **Docker**: Application containerization
- **Docker Compose**: Multi-service orchestration
- **Nginx**: Reverse proxy container
- **PostgreSQL**: Database container
- **Redis**: Cache container

## Development Commands

### Environment Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Environment configuration
cp .env.example .env
```

### Database Operations
```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load sample data
python manage.py loaddata fixtures/sample_data.json
```

### Development Server
```bash
# Run development server
python manage.py runserver 0.0.0.0:8000

# Run with specific settings
python manage.py runserver --settings=config.settings.development
```

### Background Tasks
```bash
# Start Celery worker
celery -A config worker -l info

# Start Celery beat (scheduler)
celery -A config beat -l info

# Monitor tasks
celery -A config flower
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps --cov-report=html

# Run specific test
pytest apps/core/tests/test_models.py::TestVehicleModel
```

### Code Quality
```bash
# Format code
black .
isort .

# Lint code
flake8 .

# Type checking
mypy apps/

# Security scan
bandit -r apps/
```

### Docker Development
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f web

# Run commands in container
docker-compose exec web python manage.py migrate

# Rebuild containers
docker-compose build --no-cache
```

### Production Deployment
```bash
# Collect static files
python manage.py collectstatic --noinput

# Run production server
gunicorn config.wsgi:application --bind 0.0.0.0:8000

# Database backup
pg_dump vehicle_insurance > backup.sql
```

## Build System
- **pip**: Python package management
- **requirements.txt**: Dependency specification
- **Django Management Commands**: Custom build and deployment commands
- **Docker Multi-stage builds**: Optimized production images

## Environment Configuration
- **Development**: Debug enabled, local database, detailed logging
- **Production**: Security hardened, PostgreSQL, error tracking
- **Testing**: In-memory database, test-specific settings
- **Performance**: Caching enabled, query optimization, compression

## Version Requirements
- **Python**: 3.12+
- **Django**: 5.0.1
- **PostgreSQL**: 14+
- **Redis**: 6+
- **Node.js**: Not required (no build process for frontend)

## Performance Optimizations
- **Database connection pooling**: pgbouncer compatibility
- **Query optimization**: select_related/prefetch_related usage
- **Redis caching**: Multi-level caching strategy
- **Static file compression**: WhiteNoise with gzip
- **Background processing**: Celery for heavy operations