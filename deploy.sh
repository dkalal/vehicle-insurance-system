#!/bin/bash

# Vehicle Insurance System Deployment Script
# World-class deployment automation with comprehensive checks

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="vehicle-insurance-system"
DOCKER_COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="./backups"
LOG_FILE="./logs/deployment.log"

# Functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

# Pre-deployment checks
pre_deployment_checks() {
    log "Starting pre-deployment checks..."
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        error "Docker is not running. Please start Docker and try again."
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker-compose >/dev/null 2>&1; then
        error "Docker Compose is not installed. Please install it and try again."
    fi
    
    # Check if .env file exists
    if [[ ! -f .env ]]; then
        error ".env file not found. Please create it from .env.example"
    fi
    
    # Check required environment variables
    required_vars=("SECRET_KEY" "DB_PASSWORD" "ALLOWED_HOSTS")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            error "Required environment variable $var is not set"
        fi
    done
    
    # Check disk space (minimum 2GB)
    available_space=$(df . | tail -1 | awk '{print $4}')
    if [[ $available_space -lt 2097152 ]]; then
        warning "Low disk space detected. Consider freeing up space."
    fi
    
    success "Pre-deployment checks completed"
}

# Create necessary directories
create_directories() {
    log "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p "$BACKUP_DIR"
    mkdir -p media
    mkdir -p staticfiles
    
    success "Directories created"
}

# Database backup
backup_database() {
    log "Creating database backup..."
    
    if docker-compose -f "$DOCKER_COMPOSE_FILE" ps db | grep -q "Up"; then
        backup_file="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).sql"
        
        docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T db pg_dump -U postgres vehicle_insurance > "$backup_file"
        
        if [[ -f "$backup_file" && -s "$backup_file" ]]; then
            success "Database backup created: $backup_file"
        else
            warning "Database backup may have failed"
        fi
    else
        log "Database container not running, skipping backup"
    fi
}

# Build and deploy
deploy() {
    log "Starting deployment..."
    
    # Pull latest images
    log "Pulling latest Docker images..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" pull
    
    # Build application
    log "Building application..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" build --no-cache web
    
    # Start services
    log "Starting services..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    
    # Wait for services to be healthy
    log "Waiting for services to be healthy..."
    sleep 30
    
    # Check service health
    check_service_health
    
    success "Deployment completed"
}

# Health checks
check_service_health() {
    log "Checking service health..."
    
    services=("db" "redis" "web" "nginx")
    
    for service in "${services[@]}"; do
        if docker-compose -f "$DOCKER_COMPOSE_FILE" ps "$service" | grep -q "Up"; then
            success "$service is running"
        else
            error "$service is not running properly"
        fi
    done
    
    # Check application health endpoint
    log "Checking application health endpoint..."
    
    max_attempts=10
    attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f http://localhost/health/ >/dev/null 2>&1; then
            success "Application health check passed"
            break
        else
            log "Health check attempt $attempt/$max_attempts failed, retrying..."
            sleep 10
            ((attempt++))
        fi
    done
    
    if [[ $attempt -gt $max_attempts ]]; then
        error "Application health check failed after $max_attempts attempts"
    fi
}

# Post-deployment tasks
post_deployment() {
    log "Running post-deployment tasks..."
    
    # Run migrations
    log "Running database migrations..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" exec web python manage.py migrate --noinput
    
    # Collect static files
    log "Collecting static files..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" exec web python manage.py collectstatic --noinput
    
    # Create superuser if needed
    if [[ "${CREATE_SUPERUSER:-false}" == "true" ]]; then
        log "Creating superuser..."
        docker-compose -f "$DOCKER_COMPOSE_FILE" exec web python manage.py createsuperuser --noinput || true
    fi
    
    # Warm up cache
    log "Warming up cache..."
    curl -s http://localhost/ >/dev/null || true
    
    success "Post-deployment tasks completed"
}

# Cleanup old images and containers
cleanup() {
    log "Cleaning up old Docker images and containers..."
    
    # Remove unused images
    docker image prune -f
    
    # Remove old backups (keep last 7 days)
    find "$BACKUP_DIR" -name "*.sql" -mtime +7 -delete 2>/dev/null || true
    
    success "Cleanup completed"
}

# Rollback function
rollback() {
    log "Rolling back deployment..."
    
    # Stop current services
    docker-compose -f "$DOCKER_COMPOSE_FILE" down
    
    # Restore from backup if available
    latest_backup=$(ls -t "$BACKUP_DIR"/*.sql 2>/dev/null | head -1)
    if [[ -n "$latest_backup" ]]; then
        log "Restoring database from backup: $latest_backup"
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d db
        sleep 10
        docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T db psql -U postgres -d vehicle_insurance < "$latest_backup"
    fi
    
    warning "Rollback completed. Please check your previous deployment."
}

# Main deployment flow
main() {
    log "Starting Vehicle Insurance System deployment"
    
    # Handle command line arguments
    case "${1:-deploy}" in
        "deploy")
            create_directories
            pre_deployment_checks
            backup_database
            deploy
            post_deployment
            cleanup
            ;;
        "rollback")
            rollback
            ;;
        "health")
            check_service_health
            ;;
        "backup")
            backup_database
            ;;
        *)
            echo "Usage: $0 {deploy|rollback|health|backup}"
            exit 1
            ;;
    esac
    
    success "Operation completed successfully"
}

# Trap errors and cleanup
trap 'error "Deployment failed at line $LINENO"' ERR

# Run main function
main "$@"