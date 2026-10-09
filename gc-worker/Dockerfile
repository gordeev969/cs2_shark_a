# syntax=docker/dockerfile:1
FROM node:22-alpine
WORKDIR /app
COPY gc-worker/package.json gc-worker/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --omit=dev --strict-ssl=true
COPY --chown=node:node gc-worker/src ./src
USER node
EXPOSE 8001
CMD ["node", "src/server.mjs"]
