FROM node:22-alpine AS build

WORKDIR /app

RUN npm install -g pnpm@9 \
    --registry=https://registry.npmmirror.com \
    --no-audit \
    --no-fund

RUN pnpm config set registry https://registry.npmmirror.com

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80