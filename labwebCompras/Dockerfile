FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --omit=dev
COPY --from=build /app/dist ./dist
# migrations rodam in-process no startup (src/migrate.ts via runner()).
COPY migrations ./migrations
EXPOSE 4001
CMD ["node", "dist/index.js"]
