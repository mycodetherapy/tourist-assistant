FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json vitest.config.ts ./
COPY src ./src
RUN npm run build

ENV API_NODE_PORT=8001
EXPOSE 8001

CMD ["node", "dist/index.js"]
