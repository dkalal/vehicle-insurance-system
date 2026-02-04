# Project Structure

## Root Directory Organization

```
vehicle-insurance-system/
├── apps/                    # Django applications (domain modules)
├── config/                  # Django configuration and settings
├── templates/               # HTML templates
├── static/                  # Static files (CSS, JS, images)
├── media/                   # User-uploaded files
├── docker/                  # Docker configuration
├── tests/                   # Test utilities and factories
├── logs/                    # Application logs
└── .amazonq/rules/          # AI assistant rules and documentation
```

## Core Applications (apps/)

### Domain Applications
- **core/**: Primary business logic (vehicles, customers, policies, payments)
- **tenants/**: Multi-tenant architecture and isolation
- **accounts/**: User management and authentication
- **audit/**: Audit logging and compliance tracking
- **notifications/**: Background notifications and alerts
- **reports/**: Reporting and analytics engine

### Infrastructure Applications
- **api/**: REST API endpoints and serializers
- **monitoring/**: Health checks and system monitoring
- **super_admin/**: Platform administration interface
- **dynamic_fields/**: Extensible field system for customization

## Configuration Structure (config/)

### Settings Organization
```
config/settings/
├── base.py          # Common settings
├── development.py   # Development environment
├── production.py    # Production environment
├── security.py      # Security configurations
└── performance.py   # Performance optimizations
```

### Core Configuration Files
- **urls.py**: URL routing configuration
- **wsgi.py**: WSGI application entry point
- **asgi.py**: ASGI application for async support
- **celery.py**: Background task configuration

## Template Structure (templates/)

### Template Organization
```
templates/
├── base.html              # Base template with common layout
├── dashboard/             # Main application templates
├── accounts/              # Authentication templates
├── super_admin/           # Platform admin templates
├── onboarding/            # User onboarding flow
└── errors/                # Error page templates
```

## Core Components and Relationships

### Multi-Tenant Architecture
- **Tenant Model**: Central tenant management
- **Tenant Middleware**: Automatic tenant context injection
- **Tenant Managers**: Automatic data scoping
- **Tenant Services**: Business logic isolation

### Domain Model Relationships
```
Vehicle (Root Entity)
├── Customer (Owner)
├── Policy (Insurance)
├── Payment (Financial)
├── VehicleRecord (LATRA/Permits)
└── AuditLog (History)
```

### Service Layer Architecture
- **Domain Services**: Business logic encapsulation
- **Import Services**: Data import and validation
- **Notification Services**: Alert and communication handling
- **Report Services**: Analytics and report generation

## Architectural Patterns

### Modular Monolith
- Domain-based Django applications
- Clear separation of concerns
- Service layer for business logic
- Repository pattern for data access

### Multi-Tenancy Pattern
- Single database with tenant isolation
- Row-level security via tenant_id
- Tenant-aware managers and querysets
- Middleware-based tenant context

### Security Architecture
- Role-based access control (RBAC)
- Tenant-scoped permissions
- Audit logging for all mutations
- Session security and CSRF protection

### Performance Architecture
- Redis caching layers
- Database query optimization
- Background task processing
- Static file optimization

## Development Structure

### Testing Organization
```
tests/
├── factories.py     # Test data factories
└── [app]/
    ├── test_models.py
    ├── test_views.py
    └── test_services.py
```

### Docker Configuration
```
docker/
├── nginx/           # Reverse proxy configuration
├── Dockerfile       # Application container
└── docker-compose.yml  # Development orchestration
```

## Data Flow Architecture

### Request Flow
1. **Nginx**: Reverse proxy and static file serving
2. **Django Middleware**: Authentication, tenant context, security
3. **Views**: Request handling and response formatting
4. **Services**: Business logic execution
5. **Models**: Data persistence and validation

### Background Processing
1. **Celery Workers**: Async task execution
2. **Redis**: Message broker and result backend
3. **Scheduled Tasks**: Periodic notifications and cleanup
4. **Monitoring**: Task status and error handling

## Integration Points

### External Systems
- **Database**: PostgreSQL with connection pooling
- **Cache**: Redis for session and application caching
- **File Storage**: Local media storage with cloud-ready architecture
- **Monitoring**: Health check endpoints for external monitoring

### API Architecture
- **REST API**: Django REST Framework
- **Authentication**: Session-based and token authentication
- **Documentation**: Auto-generated OpenAPI/Swagger docs
- **Rate Limiting**: Configurable API throttling