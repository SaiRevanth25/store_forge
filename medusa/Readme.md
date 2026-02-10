# Medusa Backend and Storefront

This directory contains Medusa e-commerce backend and storefront configurations used by Store Forge for provisioning e-commerce stores.

## Directories

proj-medusa/: Medusa backend server implementation
- Backend API endpoints
- Admin panel configuration
- Custom API routes and modules
- Integration tests

my-medusa-storefront/: Medusa storefront (Next.js)
- Customer-facing storefront
- Product catalog
- Shopping cart functionality
- **Important** - Need to setup NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY in the .env from the store backend/admin
    - Find in settings after loggin in to the admin dashboard
    - prefering manual key setpup for multi-purpose usecases

Setting up frontend for storefront
- From the `my-medusa-storefront` directory, run
```
yarn install
yarn dev
```


k8s/: Kubernetes manifests for deployment
- Medusa backend deployment
- PostgreSQL database setup
- Secrets management

## Setup

Refer to the main Store Forge documentation (../Readme.md) for setup instructions.

## Customization

The Medusa backend and storefront can be customized through:

- Environment variables in values.yaml
- Custom modules in src/modules/
- Custom API routes in src/api/
- Custom subscribers in src/subscribers/
- Custom workflows in src/workflows/

## Database

Database migrations are located in:

- backend/migrations/: Alembic migration scripts
- proj-medusa/: Medusa-specific schema definitions
