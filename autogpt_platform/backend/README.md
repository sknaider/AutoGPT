# AutoGPT Platform Backend

Enterprise-grade backend service for the AutoGPT Platform, built with FastAPI, PostgreSQL, Redis, and RabbitMQ.

> **Quick Start**: [Getting Started Guide](https://docs.agpt.co/platform/getting-started/#autogpt_agent_server)

## 📋 Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Security Features](#security-features)
- [Development Guide](#development-guide)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture

### Microservices Architecture

The backend is organized as a collection of specialized microservices:

```
├── rest_server (port 8006)      - Main API server
├── executor (port 8002)         - Graph execution engine
├── websocket_server (port 8001) - Real-time communication
├── database_manager (port 8005) - Database operations
├── scheduler_server (port 8003) - Scheduled tasks
└── notification_server (port 8007) - Email/notifications
```

### Key Components

- **Blocks System**: Extensible plugin architecture with 242+ blocks
- **Graph Execution**: Async workflow execution with state management
- **Authentication**: Supabase Auth with JWT tokens
- **Caching**: Multi-layer caching (Redis + in-memory)
- **Messaging**: RabbitMQ for async communication
- **Monitoring**: Prometheus metrics + Sentry error tracking

---

## 🛠️ Tech Stack

### Core

- **Framework**: FastAPI 0.116+ (async/await)
- **Language**: Python 3.10-3.13
- **ORM**: Prisma (Python client)
- **Database**: PostgreSQL 15.8 + pgvector
- **Cache**: Redis 6.2+
- **Message Queue**: RabbitMQ (aio-pika)
- **Task Scheduler**: APScheduler

### Security

- **Authentication**: Supabase Auth (GoTrue) + JWT
- **File Scanning**: ClamAV integration
- **Encryption**: Fernet (symmetric encryption)
- **CSRF Protection**: Double-submit cookie pattern
- **HTTPS Enforcement**: Automatic redirects + HSTS

### Monitoring & Observability

- **Metrics**: Prometheus
- **Error Tracking**: Sentry (100% sampling)
- **Logging**: Structured logging (Google Cloud compatible)
- **Feature Flags**: LaunchDarkly
- **APM**: Sentry Profiling

### AI & Integrations

- **LLM Providers**: OpenAI, Anthropic, Groq
- **Code Execution**: E2B
- **Image Generation**: Replicate, Fal
- **Memory**: Mem0ai
- **Social**: Ayrshare (multi-platform posting)

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Poetry 2.1.1
- Docker & Docker Compose
- PostgreSQL 15.8
- Redis 6.2+
- RabbitMQ

### Installation

1. **Clone the repository**

```bash
cd autogpt_platform/backend
```

2. **Install dependencies**

```bash
poetry install
```

3. **Set up environment**

```bash
cp .env.default .env
# Edit .env with your configuration
```

4. **Generate Prisma client**

```bash
poetry run prisma generate
```

5. **Start infrastructure services**

```bash
docker-compose up -d postgres redis rabbitmq clamav
```

6. **Run database migrations**

```bash
poetry run prisma migrate deploy
```

7. **Start the development server**

```bash
poetry run python -m backend.rest
```

The API will be available at `http://localhost:8006`

---

## 🔒 Security Features (Enterprise)

### CSRF Protection

Protects against Cross-Site Request Forgery attacks using double-submit cookie pattern.

- **Enabled by default** in production
- Automatic token rotation
- Exempt routes: `/health`, `/metrics`, OAuth callbacks, webhooks
- Header: `X-CSRF-Token`

Configuration:
```python
# backend/util/settings.py
enable_csrf_protection: bool = True
```

### HTTPS Enforcement

Automatic HTTP to HTTPS redirection in production environments.

- **HSTS** headers with 2-year max-age
- Preload-ready configuration
- Proxy-aware (respects `X-Forwarded-Proto`)

Configuration:
```python
enforce_https: bool = True
environment: str = "production"
```

### Secrets Management

Enterprise secrets validation system ensures:

- ✅ Required secrets are present
- ✅ Secrets are not default values
- ✅ Minimum length requirements met
- ✅ Strong secrets enforced in production

**Generate secure secrets:**
```bash
poetry run python -m backend.util.secrets_validator
```

**Required secrets:**
- `SUPABASE_JWT_SECRET` (min 32 chars)
- `POSTGRES_PASSWORD` (min 16 chars, not default)
- `FERNET_KEY` (min 32 chars)
- `SUPABASE_SERVICE_ROLE_KEY` (production only)

### Security Headers

All responses include comprehensive security headers:

- `Strict-Transport-Security` (HSTS)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection`
- `Content-Security-Policy`
- `Permissions-Policy`

### Exception Handling

Enterprise exception hierarchy with:

- Structured error codes
- HTTP status mapping
- User-friendly messages
- Debug details for logging

```python
from backend.util.exceptions import (
    ValidationError,
    AuthenticationError,
    ResourceNotFoundError,
    RateLimitExceededError
)

try:
    # Your code
except SomeError as e:
    raise ValidationError(
        message="Invalid input",
        error_code="CUSTOM_CODE",
        debug_details={"field": "email"}
    )
```

---

## 💻 Development Guide

### Project Structure

```
backend/
├── backend/
│   ├── blocks/              # 242+ plugin blocks
│   │   ├── ayrshare/       # Social media posting
│   │   ├── google/         # Gmail, Sheets, Drive
│   │   ├── github/         # GitHub integration
│   │   └── ...
│   ├── data/               # Data layer (Prisma)
│   ├── executor/           # Graph execution engine
│   ├── integrations/       # Third-party integrations
│   ├── monitoring/         # Metrics & instrumentation
│   ├── server/             # FastAPI app & routes
│   │   ├── middleware/    # Custom middleware
│   │   ├── routers/       # API routes
│   │   └── v2/            # API v2
│   └── util/              # Utilities
├── migrations/            # Prisma migrations
├── schema.prisma         # Database schema
├── pyproject.toml        # Dependencies
└── README.md             # This file
```

### Code Style

We use strict linting and formatting:

```bash
# Run linter (checks only)
poetry run lint

# Auto-format + check remaining issues
poetry run format
```

**Tools:**
- `ruff` - Fast linter (replaces Flake8 + many plugins)
- `black` - Code formatter (line length: 88)
- `isort` - Import sorting
- `pyright` - Static type checking

### Adding a New Block

1. Create a new file in `backend/blocks/<category>/`
2. Inherit from `Block` base class
3. Define input/output schemas with Pydantic
4. Implement `run()` method
5. Block auto-registers via `@SchemaRegistry.register`

Example:
```python
from backend.data.block import Block, BlockOutput, BlockSchema

class MyBlock(Block):
    class Input(BlockSchema):
        text: str

    class Output(BlockSchema):
        result: str

    async def run(
        self, input_data: Input, *, user_id: str, **kwargs
    ) -> BlockOutput:
        # Your logic here
        yield "result", f"Processed: {input_data.text}"
```

### Database Migrations

```bash
# Create migration
poetry run prisma migrate dev --name <migration_name>

# Apply migrations
poetry run prisma migrate deploy

# Reset database (⚠️ destroys data)
poetry run prisma migrate reset
```

### Environment Variables

Key environment variables (see `.env.default`):

**Database:**
- `POSTGRES_SERVER`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`

**Services:**
- `REDIS_HOST`
- `REDIS_PORT`
- `RABBITMQ_URI`

**Authentication:**
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`

**Security:**
- `FERNET_KEY` (encryption)
- `ENABLE_CSRF_PROTECTION`
- `ENFORCE_HTTPS`
- `ENVIRONMENT`

**LLM Providers:**
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GROQ_API_KEY`

---

## 📚 API Documentation

### Interactive API Docs

When running locally, access interactive documentation:

- **Swagger UI**: `http://localhost:8006/docs`
- **ReDoc**: `http://localhost:8006/redoc`

### API Versioning

- **v1**: `/api/*` - Legacy endpoints
- **v2**: `/api/v2/*` - Current version

### Authentication

All authenticated endpoints require a Bearer token:

```bash
curl -H "Authorization: Bearer <your_jwt_token>" \
     http://localhost:8006/api/v2/library/agents
```

### Common Endpoints

**Health Check:**
```
GET /health
```

**Metrics (Prometheus):**
```
GET /metrics
```

**List Blocks:**
```
GET /api/blocks
```

**Execute Graph:**
```
POST /api/graphs/{graph_id}/execute
```

**Store Agents:**
```
GET /api/store/agents?page=1&page_size=20
```

---

## 🧪 Testing

### Run Tests

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=backend --cov-report=html

# Specific test file
poetry run pytest backend/data/graph_test.py

# Watch mode (re-run on changes)
poetry run ptw
```

### Test Types

- **Unit Tests**: `backend/**/test_*.py`
- **Integration Tests**: `backend/**/*_integration_test.py`
- **E2E Tests**: `test/e2e_test_data.py`

### Test Database

Tests use a separate test database:

```bash
# Start test database
docker-compose -f docker-compose.test.yaml up -d

# Reset test database
poetry run prisma migrate reset --skip-seed
```

---

## 🚢 Deployment

### Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Enable `ENFORCE_HTTPS=true`
- [ ] Enable `ENABLE_CSRF_PROTECTION=true`
- [ ] Set strong secrets (not defaults!)
- [ ] Configure Sentry DSN
- [ ] Set up monitoring/alerting
- [ ] Configure backup strategy
- [ ] Review rate limits
- [ ] Enable auto-scaling
- [ ] Set up SSL certificates

### Docker Deployment

Build the Docker image:

```bash
docker build -t autogpt-backend -f Dockerfile .
```

Run with Docker Compose:

```bash
cd autogpt_platform
docker-compose up -d
```

### Environment-Specific Configuration

**Local:**
```env
ENVIRONMENT=local
ENFORCE_HTTPS=false
ENABLE_CSRF_PROTECTION=false
VALIDATE_SECRETS_ON_STARTUP=false
```

**Production:**
```env
ENVIRONMENT=production
ENFORCE_HTTPS=true
ENABLE_CSRF_PROTECTION=true
VALIDATE_SECRETS_ON_STARTUP=true
REQUIRE_STRONG_SECRETS=true
```

### Performance Tuning

**FastAPI Thread Pool:**
```env
# Increase for more concurrent sync operations
FASTAPI_THREAD_POOL_SIZE=60  # Default: 60
```

**Graph Workers:**
```env
# Number of parallel graph execution workers
NUM_GRAPH_WORKERS=10  # Default: 10
```

**Database Connections:**
```env
DB_CONNECTION_LIMIT=50  # Prisma connection pool
DB_POOL_TIMEOUT=40  # Connection acquisition timeout
```

**Max Concurrent Executions:**
```env
MAX_CONCURRENT_GRAPH_EXECUTIONS_PER_USER=25
```

---

## 🐛 Troubleshooting

### Common Issues

**1. Database connection failed**

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check connection
poetry run prisma db pull
```

**2. Prisma client not generated**

```bash
poetry run prisma generate
```

**3. Migration conflicts**

```bash
# Reset and re-apply migrations
poetry run prisma migrate reset
poetry run prisma migrate deploy
```

**4. Redis connection failed**

```bash
# Start Redis
docker-compose up -d redis

# Test connection
redis-cli ping
```

**5. RabbitMQ not accessible**

```bash
# Start RabbitMQ
docker-compose up -d rabbitmq

# Check management UI
open http://localhost:15672  # guest/guest
```

**6. Import errors**

```bash
# Reinstall dependencies
poetry install --no-cache
```

**7. Secrets validation failing**

```bash
# Generate new secrets
poetry run python -m backend.util.secrets_validator

# Or disable in development
export VALIDATE_SECRETS_ON_STARTUP=false
```

### Logs

**View application logs:**
```bash
tail -f backend/logs/activity.log
tail -f backend/logs/error.log
```

**Docker logs:**
```bash
docker-compose logs -f rest_server
docker-compose logs -f executor
```

### Debug Mode

Enable asyncio debug mode (local only):

```env
ENVIRONMENT=local
PYTHONASYNCIODEBUG=1
```

---

## 📈 Monitoring

### Prometheus Metrics

Metrics available at `/metrics`:

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `graph_executions_total` - Graph executions by status
- `block_executions_total` - Block executions by type
- `block_execution_duration_seconds` - Block execution time
- `websocket_connections` - Active WebSocket connections
- `db_query_duration_seconds` - Database query latency
- `rate_limit_hits_total` - Rate limit violations

### Sentry Error Tracking

All exceptions are automatically reported to Sentry (if configured):

```env
SENTRY_DSN=https://...@sentry.io/...
```

Features:
- 100% error sampling
- 100% transaction tracing
- Profiling enabled
- User context tracking
- Release tracking

### Health Checks

**Endpoint**: `GET /health`

Returns:
```json
{
  "status": "healthy"
}
```

Checks:
- Database connectivity
- Redis connectivity
- RabbitMQ connectivity

---

## 🤝 Contributing

1. Follow the code style (run `poetry run format`)
2. Add tests for new features
3. Update documentation
4. Create a pull request

### Commit Message Format

We use Conventional Commits:

```
feat: add new block for X
fix: resolve Y issue
docs: update README
refactor: simplify Z logic
test: add tests for W
```

---

## 📝 License

This project is licensed under the Polyform Shield License.

---

## 🆘 Support

- **Documentation**: https://docs.agpt.co
- **Issues**: https://github.com/Significant-Gravitas/AutoGPT/issues
- **Discord**: https://discord.gg/autogpt

---

## 🎯 Enterprise Features Summary

✅ **Security:**
- CSRF protection
- HTTPS enforcement
- Secrets validation
- Security headers
- JWT authentication
- File virus scanning

✅ **Performance:**
- Redis caching
- Connection pooling
- Async I/O
- Rate limiting
- Load balancing ready

✅ **Observability:**
- Prometheus metrics
- Sentry error tracking
- Structured logging
- Health checks
- Feature flags

✅ **Reliability:**
- Graceful shutdown
- Circuit breakers
- Retry logic
- Dead letter queues
- Data encryption

---

*Built with ❤️ by the AutoGPT team*
