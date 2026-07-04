import Fastify, { FastifyInstance } from 'fastify';
import { SalesController } from './modules/sales/controllers/SalesController';
import { validateConfig } from './config/env';
import { IdempotencyRepository } from './modules/sales/repositories/IdempotencyRepository';
import { ProductsRepository } from './modules/sales/repositories/ProductsRepository';
import { database } from './shared/database/database';

// Validação inicial das variáveis
validateConfig();

export const app: FastifyInstance = Fastify({
  logger: process.env.NODE_ENV === 'test' ? false : true // Desativa logs em ambiente de teste 
});

const productsRepository = new ProductsRepository();
const idempotencyRepository = new IdempotencyRepository(database.getPool());

// Tratamento global de erros
app.setErrorHandler((error: any, request, reply) => {
  request.log.error(error);

  if (error.validation) {
    return reply.status(400).send({
      error: 'Bad Request',
      message: 'Erro de validação nos parâmetros de entrada',
      details: error.validation
    });
  }

  return reply.status(500).send({
    error: 'Internal Server Error',
    message: 'Ocorreu um erro interno no servidor.'
  });
});

const salesController = new SalesController();

app.post('/v1/sales', {
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

app.get('/v1/products', async (request, reply) => {
  try {
    const products = await productsRepository.findAll(database.getPool());
    return reply.status(200).send(products);
  } catch (error) {
    request.log.error(error);
    return reply.status(500).send({ error: 'Erro ao buscar produtos' });
  }
});

app.get('/v1/idempotency', async (request, reply) => {
  try {
    const outboxRecords = await idempotencyRepository.getAllFromPostgres();
    return reply.status(200).send(outboxRecords);
  } catch (error) {
    request.log.error(error);
    return reply.status(500).send({ error: 'Erro ao buscar registros de idempotência' });
  }
});