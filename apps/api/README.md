# Plinto API

This directory will contain the FastAPI/Python backend for the Plinto authentication platform.

## Structure

```
apps/api/
├── main.py           # FastAPI application entry point
├── routers/          # API route handlers
├── models/           # Database models (SQLAlchemy)
├── services/         # Business logic
├── middleware/       # Authentication, CORS, etc.
├── alembic/          # Database migrations
└── tests/            # API tests
```

## Tech Stack

- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Primary database
- **Redis** - Session cache and rate limiting
- **SQLAlchemy** - ORM
- **Alembic** - Database migrations
- **SuperTokens Core** - Authentication engine
- **OPA** - Policy engine

## Deployment

The API will be deployed to Railway and accessed via:
- `api.plinto.dev` - Production API endpoint

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload

# Run migrations
alembic upgrade head
```