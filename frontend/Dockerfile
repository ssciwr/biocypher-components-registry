FROM node:24-alpine AS build

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN pnpm run build

FROM nginx:1.27-alpine

ENV BACKEND_INTERNAL_URL=http://backend:8000
ENV FRONTEND_SERVER_NAME=registry.biocypher.org
ENV TLS_CERTIFICATE_PATH=/etc/letsencrypt/live/registry.biocypher.org/fullchain.pem
ENV TLS_CERTIFICATE_PRIV_PATH=/etc/letsencrypt/live/registry.biocypher.org/privkey.pem
COPY nginx.conf /etc/nginx/template-options/default.conf.https.template
COPY nginx-http.conf /etc/nginx/template-options/default.conf.http.template
COPY docker-entrypoint.d/04-select-nginx-template.sh /docker-entrypoint.d/04-select-nginx-template.sh
RUN mkdir -p /etc/nginx/templates \
    && chown -R nginx:nginx /etc/nginx/templates /etc/nginx/conf.d /var/cache/nginx /var/run \
    && chmod +x /docker-entrypoint.d/04-select-nginx-template.sh
COPY --from=build /app/dist /usr/share/nginx/html

USER nginx

EXPOSE 80 443
