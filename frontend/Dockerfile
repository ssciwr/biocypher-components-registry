FROM node:24-alpine AS build

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY index.html tsconfig.app.json tsconfig.json tsconfig.node.json vite.config.ts ./
COPY public ./public
COPY src ./src
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN pnpm run build

FROM nginx:1.27-alpine

ENV BACKEND_INTERNAL_URL=http://backend:8000
COPY --chown=nginx:nginx nginx.conf /etc/nginx/templates/default.conf.template
COPY --chown=nginx:nginx --from=build /app/dist /usr/share/nginx/html
RUN touch /var/run/nginx.pid \
    && chown -R nginx:nginx /etc/nginx/conf.d /etc/nginx/templates /usr/share/nginx/html /var/cache/nginx /var/log/nginx /var/run/nginx.pid
USER nginx

EXPOSE 80
