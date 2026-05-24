FROM node:20-alpine AS deps
WORKDIR /app
COPY services/ui/package.json ./
RUN npm install

FROM node:20-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_RETRAIN_API_TOKEN=
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_PUBLIC_RETRAIN_API_TOKEN=${NEXT_PUBLIC_RETRAIN_API_TOKEN}
COPY --from=deps /app/node_modules ./node_modules
COPY services/ui ./
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app ./
EXPOSE 3001
CMD ["npm", "run", "start"]

