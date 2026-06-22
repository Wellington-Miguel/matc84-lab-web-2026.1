import { app } from './app';
import { IdempotencyWorker } from './shared/services/IdempotencyWorker';
import { config } from './config/env';
import { database } from './shared/database/database';

const start = async () => {
  try {
    const port = config.port;
    const host = '0.0.0.0';

    await app.listen({ port, host });
    console.log(`🚀 Servidor rodando em http://localhost:${port}`);

    // Inicia o worker de idempotência em background
    if (config.dynamoTableName) {
      IdempotencyWorker.getInstance().start();
    } else {
      console.log(
        '[Server] Aviso: DYNAMO_TABLE_NAME não configurada no ambiente. IdempotencyWorker não iniciado.'
      );
    }
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
};

const shutdown = async (signal: string) => {
  console.log(`\n[Server] Recebido sinal ${signal}. Iniciando desligamento gracioso...`);
  
  try {
    IdempotencyWorker.getInstance().stop();
    console.log('-> IdempotencyWorker interrompido.');
  } catch (e) {
    console.error('-> Erro ao parar IdempotencyWorker:', e);
  }

  try {
    await app.close();
    console.log('-> Servidor Fastify encerrado.');
  } catch (e) {
    console.error('-> Erro ao encerrar Fastify:', e);
  }

  try {
    await database.getPool().end();
    console.log('-> Pool de conexões do PostgreSQL fechado.');
  } catch (e) {
    console.error('-> Erro ao fechar pool do PostgreSQL:', e);
  }

  console.log('✨ Servidor desligado com sucesso!');
  process.exit(0);
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

start();
