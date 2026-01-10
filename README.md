# Vehicle Insurance Information System

A world-class, multi-tenant insurance information system built with Django, designed for real-world production use with enterprise-grade security, performance, and scalability.

## 🏗️ Architecture Overview

### Multi-Tenant Architecture
- **Single Database, Tenant Isolation**: Each insurance company (tenant) has complete data isolation
- **Tenant-Aware Models**: All business models automatically scope to current tenant
- **Middleware-Based Context**: Tenant context automatically set from authenticated user
- **Scalable Design**: Supports thousands of tenants on single infrastructure

### Security Features
- **Role-Based Access Control**: Super Admin, Tenant Admin, Manager, Agent roles
- **Session Security**: Secure session management with rotation and expiry
- **Rate Limiting**: Login attempt limiting and API throttling
- **CSRF Protection**: Comprehensive CSRF protection across all forms
- **Content Security Policy**: Strict CSP headers for XSS prevention
- **Audit Logging**: Complete audit trail of all data changes

### Performance Optimizations
- **Redis Caching**: Multi-level caching strategy for optimal performance
- **Database Optimization**: Connection pooling, query optimization, indexes
- **Async Processing**: Celery for background tasks and notifications
- **Static File Optimization**: WhiteNoise with compression and caching
- **Query Optimization**: Select/prefetch related, bulk operations

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 14+
- Redis 6+
- Docker & Docker Compose (optional)

### Local Development Setup

```bash
# Clone repository
git clone <repository-url>
cd Vehicle_Insurance

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Environment setup
cp .env.example .env
# Edit .env with your database and Redis settings

# Database setup
python manage.py migrate
python manage.py createsuperuser

# Create initial tenant (optional)
python manage.py shell
>>> from apps.tenants.models import Tenant
>>> tenant = Tenant.objects.create(name="Demo Insurance", slug="demo", contact_email="admin@demo.com")

# Run development server
python manage.py runserver 0.0.0.0:8000
```

### Docker Development Setup

```bash
# Start all services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Access application at http://localhost
```

## 📊 System Features

### Core Business Logic
- **Customer Management**: Individual and corporate customer profiles
- **Vehicle Registration**: Complete vehicle information with VIN tracking
- **Policy Management**: Comprehensive policy lifecycle management
- **Payment Processing**: Payment tracking with verification workflow
- **Claims Processing**: (Extensible framework ready)

### Business Rules Implementation
- ✅ One active policy per vehicle at any time
- ✅ Full payment required before policy activation
- ✅ Immutable policy history (soft deletes only)
- ✅ Automatic policy number generation per tenant
- ✅ Expiry notifications and reminders

### Reporting & Analytics
- **Policy Reports**: Comprehensive policy analytics with export (CSV, XLSX, PDF)
- **Registration Reports**: Vehicle registration tracking
- **Revenue Analytics**: Premium collection and revenue tracking
- **Dashboard Metrics**: Real-time business metrics
- **Audit Reports**: Complete audit trail reporting

### API & Integration
- **RESTful API**: Complete REST API with DRF
- **API Documentation**: Auto-generated OpenAPI/Swagger docs
- **Authentication**: Session-based and token authentication
- **Rate Limiting**: Configurable API rate limiting
- **Filtering & Search**: Advanced filtering and search capabilities

## 🔧 Technical Stack

### Backend
- **Django 5.0**: Modern Python web framework
- **Django REST Framework**: API development
- **PostgreSQL**: Primary database with advanced features
- **Redis**: Caching and message broker
- **Celery**: Asynchronous task processing

### Frontend
- **Tailwind CSS**: Modern utility-first CSS framework
- **Alpine.js**: Lightweight JavaScript framework
- **Responsive Design**: Mobile-first responsive design
- **Accessibility**: WCAG 2.1 AA compliant

### Infrastructure
- **Docker**: Containerization for all services
- **Nginx**: Reverse proxy and static file serving
- **Gunicorn**: WSGI HTTP Server
- **WhiteNoise**: Static file serving with compression

### Monitoring & Observability
- **Health Checks**: Comprehensive health monitoring endpoints
- **Metrics**: Prometheus-compatible metrics
- **Logging**: Structured logging with rotation
- **Performance Monitoring**: Built-in performance tracking

## 🏢 Multi-Tenancy Details

### Tenant Isolation
```python
# All models automatically scope to tenant
customers = Customer.objects.all()  # Only current tenant's customers
policies = Policy.objects.for_tenant(tenant)  # Explicit tenant filtering
```

### User Roles & Permissions
- **Super Admin**: Platform management, tenant creation, system monitoring
- **Tenant Admin**: Full access within tenant, user management
- **Manager**: Read access, reporting, staff management
- **Agent**: Customer/vehicle/policy creation, payment processing

### Tenant-Specific Features
- Custom domains per tenant (configurable)
- Tenant-specific settings and configurations
- Branded UI per tenant (extensible)
- Separate audit logs per tenant

## 🔒 Security Implementation

### Authentication & Authorization
```python
# Automatic tenant context in views
@login_required
def customer_list(request):
    # request.tenant automatically available
    customers = Customer.objects.for_tenant(request.tenant)
```

### Data Protection
- All sensitive data encrypted at rest
- PII data handling with privacy controls
- GDPR compliance framework
- Secure file upload handling

### Security Headers
- Content Security Policy (CSP)
- HTTP Strict Transport Security (HSTS)
- X-Frame-Options, X-Content-Type-Options
- Referrer Policy controls

## 📈 Performance Features

### Caching Strategy
```python
# Multi-level caching
CACHES = {
    'default': {...},      # General application cache
    'sessions': {...},     # Session storage
    'tenant_data': {...},  # Tenant-specific data cache
}
```

### Database Optimization
- Connection pooling with pgbouncer compatibility
- Query optimization with select_related/prefetch_related
- Database indexes on all foreign keys and search fields
- Bulk operations for large datasets

### Background Processing
```python
# Celery tasks for heavy operations
@shared_task
def send_expiry_reminders():
    # Process policy expiry notifications
    pass

@shared_task
def generate_monthly_reports():
    # Generate and email monthly reports
    pass
```

## 🧪 Testing Strategy

### Test Coverage
- Unit tests for all models and business logic
- Integration tests for API endpoints
- Tenant isolation tests
- Performance tests for scalability
- Security tests for vulnerabilities

### Test Utilities
```python
# Comprehensive test factories
from tests.factories import TenantFactory, UserFactory, PolicyFactory

def test_policy_activation():
    tenant = TenantFactory()
    policy = PolicyFactory(tenant=tenant)
    # Test policy activation logic
```

## 🚀 Deployment

### Production Deployment
```bash
# Using Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# Or traditional deployment
pip install -r requirements.txt
python manage.py collectstatic
python manage.py migrate
gunicorn config.wsgi:application
```

### Environment Variables
```bash
# Required production settings
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
DB_HOST=your-db-host
REDIS_URL=redis://your-redis-host:6379/0
```

### Monitoring Setup
- Health check endpoints: `/health/`, `/health/ready/`, `/health/live/`
- Metrics endpoint: `/health/metrics/`
- Prometheus integration ready
- Grafana dashboards included

## 📚 API Documentation

### Authentication
```bash
# Session-based authentication
curl -X POST http://localhost:8000/api/auth/login/ \
  -d "username=admin&password=password"

# API endpoints
curl -H "Authorization: Token your-token" \
  http://localhost:8000/api/v1/customers/
```

### Available Endpoints
- `/api/v1/customers/` - Customer management
- `/api/v1/vehicles/` - Vehicle management  
- `/api/v1/policies/` - Policy management
- `/api/v1/payments/` - Payment processing
- `/api/docs/` - Interactive API documentation

## 🔧 Configuration

### Tenant Settings
```python
# Tenant-specific configurations
tenant.set_setting('expiry_reminder_days', 30)
tenant.set_setting('auto_renewal_enabled', True)
tenant.set_setting('payment_grace_period', 7)
```

### Feature Flags
```python
# Feature toggles per tenant
if tenant.get_setting('fleet_policies_enabled'):
    # Enable fleet policy features
    pass
```

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes with tests
4. Run test suite: `pytest`
5. Submit pull request

### Code Quality
```bash
# Code formatting
black .
isort .

# Linting
flake8 .

# Type checking
mypy .

# Security scanning
bandit -r apps/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation
- [API Documentation](http://localhost:8000/api/docs/)
- [Admin Guide](docs/admin-guide.md)
- [Developer Guide](docs/developer-guide.md)

### Getting Help
- Create an issue for bugs or feature requests
- Check existing documentation
- Review test cases for usage examples

---

**Built with ❤️ for the insurance industry**

This system represents world-class software engineering practices with enterprise-grade security, performance, and maintainability. Every component has been carefully designed for production use at scale.