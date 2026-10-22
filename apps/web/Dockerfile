# Chess Engine Web — production image (REL-001).
# Stage 1: build the static bundle.
FROM node:20-alpine AS build
WORKDIR /srv/web
COPY package.json package-lock.json ./
RUN npm ci
COPY . ./
RUN npm run build

# Stage 2: serve over HTTP as an unprivileged user (Phase 5 hardening). The
# `nginx-unprivileged` image listens on 8080 and runs the worker as non-root;
# TLS still terminates at the reverse proxy in front of it (REL-003).
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY --from=build /srv/web/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
