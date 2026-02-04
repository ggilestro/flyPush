# flyPush - Drosophila Stock Management System

## Project Overview
A SaaS web application for managing Drosophila (fruit fly) stocks in research laboratories. Multi-tenant architecture supporting multiple labs as customers, with PWA support for desktop and mobile use.

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI (Python 3.11+) |
| Database | MariaDB 10.11+ (Docker) |
| ORM | SQLAlchemy 2.0 + Alembic migrations |
| Auth | JWT tokens (python-jose) + passlib for passwords |
| Frontend | Jinja2 templates + HTMX + Alpine.js |
| PWA | Service Worker + Web App Manifest |
| Containers | Docker + docker-compose |
| Validation | Pydantic v2 |

## Architecture Decisions

### Why HTMX + Alpine.js instead of React/Vue?
- Faster MVP development
- Server-side rendering = better SEO and simpler state management
- Progressive enhancement works well with PWA
- Smaller bundle size for mobile

### Multi-Tenancy Strategy
Every database query automatically filters by `tenant_id`. Each tenant (lab) has complete data isolation.

## Project Structure
```
flyPush/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic/                    # Database migrations
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Settings via pydantic-settings
│   ├── dependencies.py         # Dependency injection
│   ├── db/                     # Database layer
│   ├── auth/                   # Authentication module
│   ├── tenants/                # Tenant management
│   ├── stocks/                 # Stock CRUD
│   ├── crosses/                # Cross planning
│   ├── labels/                 # QR/barcode generation
│   ├── imports/                # CSV/Excel import
│   ├── plugins/                # External integrations (FlyBase)
│   ├── templates/              # Jinja2 templates
│   └── static/                 # CSS, JS, PWA files
└── tests/
```

## Core Entities

### Tenant
- Represents a lab/organization
- First user to register creates the tenant
- All data is scoped to tenant

### User
- Belongs to one tenant
- Roles: admin, user
- Admin can manage other users

### Stock
- Main entity for fly stocks
- Fields: stock_id, genotype, source, location, notes
- Supports tagging
- Soft delete

### Cross
- Represents a planned or completed cross
- Links two parent stocks (female, male)
- Can link to offspring stock when completed
- Status: planned, in_progress, completed, failed

## API Design

### REST Endpoints
- `/api/auth/*` - Authentication
- `/api/stocks/*` - Stock CRUD
- `/api/tags/*` - Tag management
- `/api/crosses/*` - Cross planning
- `/api/admin/*` - User management (admin only)

### HTML Pages
- `/` - Dashboard
- `/login`, `/register` - Auth pages
- `/stocks/*` - Stock management UI
- `/crosses/*` - Cross planning UI
- `/settings` - User settings
- `/admin` - Admin panel

## Development Guidelines

### Code Style
- Follow PEP8
- Use type hints everywhere
- Format with black
- Lint with ruff
- Google-style docstrings

### Testing
- Pytest for all tests
- Each feature needs: success, edge case, failure tests
- Tests mirror app structure in tests/

### Git Workflow
- Meaningful commit messages
- One logical change per commit
- Never commit secrets
