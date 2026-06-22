import Fastify from 'fastify';
import { SalesController } from './modules/sales/controllers/SalesController';
import { IdempotencyWorker } from './shared/services/IdempotencyWorker';

const fastify = Fastify({
  logger: true
});

const salesController = new SalesController();

// Define a rota POST /v1/sales mapeando para o controller com validação de esquema
fastify.post('/v1/sales', {
  schema: {
    headers: {
      type: 'object',
      required: ['x-idempotency-key'],
      properties: {
        'x-idempotency-key': { 
          type: 'string', 
          pattern: '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' 
        }
      }
    },
    body: {
      type: 'object',
      required: ['productId', 'version'],
      properties: {
        productId: { 
          type: 'string', 
          pattern: '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' 
        },
        version: { type: 'integer', minimum: 1 }
      }
    }
  }
}, async (request, reply) => {
  return salesController.create(request as any, reply);
});

const start = async () => {
  try {
    const port = Number(process.env.PORT) || 3000;
    const host = '0.0.0.0';

    await fastify.listen({ port, host });
    console.log(`🚀 Servidor rodando em http://localhost:${port}`);

    // Inicia o worker de idempotência em background
    if (process.env.DYNAMO_TABLE_NAME) {
      IdempotencyWorker.getInstance().start();
    } else {
      console.log(
        '[Server] Aviso: DYNAMO_TABLE_NAME não configurada no ambiente. IdempotencyWorker não iniciado.'
      );
    }
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
};

start();
