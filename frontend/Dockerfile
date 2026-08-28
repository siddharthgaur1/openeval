FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# NEXT_PUBLIC_* variables are inlined into the JS bundle at build time by
# `next build` - setting them via docker-compose's `environment:` (container
# runtime) has no effect, so it must be passed as a build ARG instead.
# Default matches the Render blueprint's backend service name (render.yaml
# can't pass Docker build args - Render's Blueprint spec has no such field).
# If that service name ever changes, override with `docker build --build-arg`.
ARG NEXT_PUBLIC_API_URL=https://openeval-backend.onrender.com
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
