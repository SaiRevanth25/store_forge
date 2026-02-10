# Store Forge

Store Forge is a comprehensive e-commerce store provisioning and management platform that simplifies deploying Medusa-based stores on Kubernetes clusters.

## Features

- Web-based dashboard for store management
- User registration and authentication
- One-click store provisioning and deployment
- Kubernetes and Helm integration for automated infrastructure
- Real-time provisioning status tracking
- Port-forwarding for local development access
- Store event monitoring and logging
- Support for multiple store engines (Medusa)

## Project Structure

- frontend/: React TypeScript application for the web dashboard
- backend/: FastAPI REST API service
- charts/: Helm charts for Medusa deployments
- medusa/: Medusa e-commerce backend and storefront configurations

## Getting Started

### Backend Setup

Navigate to the backend directory and follow the setup instructions in backend/Readme.md

### Frontend Setup

Navigate to the frontend directory and follow the setup instructions in frontend/README.md

### Kubernetes and Helm

Store deployments are managed through Kubernetes and Helm. Ensure your kubectl is configured to access your cluster.

## Technology Stack

Frontend:
- React 18
- TypeScript
- Tailwind CSS
- Vite

Backend:
- FastAPI
- SQLAlchemy
- PostgreSQL
- Kubernetes Python client
- Helm CLI integration

Deployment:
- Kubernetes
- Helm
- Docker

## License

See LICENSE file for details
