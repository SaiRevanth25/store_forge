# Store Forge Backend

Store Forge Backend is a FastAPI-based REST API service for provisioning and managing e-commerce stores on Kubernetes clusters.

## Features

- User authentication and authorization
- Store CRUD operations
- Kubernetes cluster integration via kubectl and Helm
- Automated store provisioning with Medusa backend
- Port-forwarding for local store access
- Store event logging and status tracking
- Database migrations with Alembic

## Architecture

The backend consists of:

- api/: REST API routes for stores and users
- services/: Business logic (provisioning service for Kubernetes operations)
- core/: Database configuration, ORM, security, and utilities
- models/: Pydantic models for request/response validation
- migrations/: Alembic database migration scripts

## Setup

### Prerequisites

- Python 3.10+
- PostgreSQL database
- Kubernetes cluster (kubectl configured)
- Helm 3.x

### Installation

- Create a virtualenv 
```
python -m venv venv
.venv/Scripts/activate.ps1
```

1. Install dependencies:
```
pip install -r requirements.txt
```
or
```
uv sync(preferred)
```

2. Configure environment variables in `.env`
- Set the DATABASE_URL=

3. Run database migrations:
```
alembic upgrade head
```
4. Start the server:
```
python main.py
```
The API will be available at http://localhost:8000

## API Documentation

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
