FROM node:20-alpine AS builder

WORKDIR /app

# NEXT_PUBLIC_ vars are baked into the client bundle at build time.
# API_URL is server-only: used by next.config.js rewrites to proxy /api/v1/*
# to the backend, avoiding mixed-content (HTTPS UI → HTTP backend) issues.
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_API_KEY
ARG NEXT_PUBLIC_WEBHOOK_GATEWAY_URL
ARG NEXT_PUBLIC_WEBHOOK_API_KEY
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG SUPABASE_AUTH_URL
ARG API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-}
ENV NEXT_PUBLIC_API_KEY=${NEXT_PUBLIC_API_KEY:-}
ENV NEXT_PUBLIC_WEBHOOK_GATEWAY_URL=${NEXT_PUBLIC_WEBHOOK_GATEWAY_URL:-}
ENV NEXT_PUBLIC_WEBHOOK_API_KEY=${NEXT_PUBLIC_WEBHOOK_API_KEY:-}
ENV NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL:-}
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=${NEXT_PUBLIC_SUPABASE_ANON_KEY:-}
ENV SUPABASE_AUTH_URL=${SUPABASE_AUTH_URL:-}
ENV API_URL=${API_URL:-}

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Ensure public directory exists (even if empty)
RUN mkdir -p public

# Build the application (NEXT_PUBLIC_API_URL gets baked into client bundle)
RUN npm run build

# Production image
FROM node:20-alpine AS runner

WORKDIR /app

# Set to production
ENV NODE_ENV=production

# Increase Node.js heap size to prevent OOM errors (1536MB leaves room for other memory usage in 2Gi container)
ENV NODE_OPTIONS="--max-old-space-size=1536"

# Copy built application from builder
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Expose port (Cloud Run uses 8080 by default)
EXPOSE 8080

ENV PORT=8080
ENV HOSTNAME="0.0.0.0"

# Start the application
CMD ["node", "server.js"]
