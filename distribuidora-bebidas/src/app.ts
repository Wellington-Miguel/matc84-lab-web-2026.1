import Fastify, { FastifyInstance } from 'fastify';
import { SalesController } from './modules/sales/controllers/SalesController';
import { validateConfig } from './config/env';

// Validação inicial das variáveis
validateConfig();

export const app: FastifyInstance = Fastify({
  logger: process.env.NODE_ENV === 'test' ? false : true // Desativa logs em ambiente de teste 
});

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
