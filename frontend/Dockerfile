FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# NEXT_PUBLIC_* variables are inlined into the JS bundle at build time by
# `next build` - setting them via docker-compose's `environment:` (container
# runtime) has no effect, so it must be passed as a build ARG instead.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
