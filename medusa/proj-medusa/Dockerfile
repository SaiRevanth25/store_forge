FROM node:20-alpine

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --no-frozen-lockfile

COPY . .

# Set env vars needed during build for admin panel
ENV STORE_CORS=http://localhost:8000
ENV ADMIN_CORS=http://localhost:9000
ENV AUTH_CORS=http://localhost:9000

# Build the full Medusa app (backend + admin)
RUN pnpm medusa build

# Install production deps inside the build output
WORKDIR /app/.medusa/server
RUN pnpm install --no-frozen-lockfile

EXPOSE 9000

# Start from the build output directory
CMD ["pnpm", "medusa", "start"]
