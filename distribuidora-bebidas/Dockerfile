# ==========================================
# Estágio 1: Dependências de Desenvolvimento e Compilação
# ==========================================
FROM node:22-alpine AS builder

# Diretório de trabalho no container
WORKDIR /usr/src/app

# arquivos de dependências copiados 
COPY package*.json ./

# Instalação das dependências 
RUN npm ci

# Copia o código-fonte e arquivos de configuração do TypeScript
COPY tsconfig.json ./
COPY src/ ./src/

# Compilação do projeto TypeScript para JavaScript na pasta /dist
RUN npm run build

# Remoção das dependências de desenvolvimento para economizar espaço
RUN npm prune --omit=dev


# ==========================================
# Estágio 2: Ambiente de Produção (Imagem Enxuta)
# ==========================================
FROM node:22-alpine AS runner

# Define variável de ambiente para otimização do Node.js
ENV NODE_ENV=production

WORKDIR /usr/src/app

# Copia as dependências de produção limpas e o código compilado do builder
COPY --from=builder /usr/src/app/package*.json ./
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY --from=builder /usr/src/app/dist ./dist

#Rodar a aplicação como um usuário não-root nativo do Alpine (node)
USER node

# Porta padrão de escuta
EXPOSE 3000

# Variável de ambiente padrão para a porta
ENV PORT=3000

# Executa o processo da aplicação diretamente
CMD ["node", "dist/index.js"]
