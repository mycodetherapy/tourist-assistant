FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY . .

# Опционально из docker compose (корневой .env); иначе web/.env при сборке.
ARG VITE_YANDEX_MAPS_API_KEY
ARG VITE_YANDEX_METRIKA_ID
RUN \
  if [ -n "$VITE_YANDEX_MAPS_API_KEY" ]; then export VITE_YANDEX_MAPS_API_KEY="$VITE_YANDEX_MAPS_API_KEY"; fi && \
  if [ -n "$VITE_YANDEX_METRIKA_ID" ]; then export VITE_YANDEX_METRIKA_ID="$VITE_YANDEX_METRIKA_ID"; fi && \
  npm run build

FROM nginx:1.27-alpine

ARG NGINX_CONF=nginx.conf
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
