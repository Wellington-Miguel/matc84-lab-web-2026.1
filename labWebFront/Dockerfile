FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# URLs das APIs embutidas no bundle (browser chama direto compras/sugestões).
ARG VITE_COMPRAS_URL=http://localhost:4001
ARG VITE_SUGESTOES_URL=http://localhost:4002
ENV VITE_COMPRAS_URL=$VITE_COMPRAS_URL
ENV VITE_SUGESTOES_URL=$VITE_SUGESTOES_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
