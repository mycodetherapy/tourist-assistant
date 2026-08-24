FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY . .

# Опционально из docker compose / CI build-args; иначе web/.env при сборке.
ARG VITE_YANDEX_MAPS_API_KEY
ARG VITE_YANDEX_METRIKA_ID
ARG VITE_YANDEX_SMARTCAPTCHA_CLIENT_KEY
# maplibre — MapLibre+OSRM при наличии route_geometry; иначе iframe Яндекса.
ARG VITE_MAP_PROVIDER=maplibre
RUN \
  if [ -n "$VITE_YANDEX_MAPS_API_KEY" ]; then export VITE_YANDEX_MAPS_API_KEY="$VITE_YANDEX_MAPS_API_KEY"; fi && \
  if [ -n "$VITE_YANDEX_METRIKA_ID" ]; then export VITE_YANDEX_METRIKA_ID="$VITE_YANDEX_METRIKA_ID"; fi && \
  if [ -n "$VITE_YANDEX_SMARTCAPTCHA_CLIENT_KEY" ]; then export VITE_YANDEX_SMARTCAPTCHA_CLIENT_KEY="$VITE_YANDEX_SMARTCAPTCHA_CLIENT_KEY"; fi && \
  export VITE_MAP_PROVIDER="${VITE_MAP_PROVIDER:-maplibre}" && \
  npm run build

FROM nginx:1.27-alpine

ARG NGINX_CONF=nginx.conf
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
