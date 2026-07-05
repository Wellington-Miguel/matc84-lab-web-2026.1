import { FastifyRequest, FastifyReply } from 'fastify';
import { CreateSaleService } from '../services/CreateSaleService';
import { database } from '../../../shared/database/database';

interface SaleRequest {
  productId: string;
  version: number;
}

export class SalesController {
  private createSaleService = new CreateSaleService(database.getPool());

  public async create(request: FastifyRequest<{ Body: SaleRequest }>, reply: FastifyReply): Promise<void> {
    const idempotencyKey = request.headers['x-idempotency-key'] as string;

    if (!idempotencyKey) {
      return reply.status(400).send({ error: 'X-Idempotency-Key header is required' });
    }

    const { productId, version } = request.body;

    let timeoutHandle: NodeJS.Timeout;
    const timeoutPromise = new Promise((_, reject) => {
      timeoutHandle = setTimeout(() => reject(new Error('TIMEOUT_LIMIT_REACHED')), 5000);
    });

    try {
      const resultPromise = this.createSaleService.execute(idempotencyKey, productId, version);

      const result = await Promise.race([
        resultPromise,
        timeoutPromise
      ]) as any;

      if (!reply.sent) {
        return reply.status(result.httpStatus).send(result.payload);
      }
    } catch (error: any) {
      if (error.message === 'TIMEOUT_LIMIT_REACHED') {
        if (!reply.sent) {
          return reply.status(504).send({ error: 'Request Timeout' });
        }
      } else {
        if (!reply.sent) {
          console.error('[SalesController] Internal Error:', error);
          return reply.status(500).send({ error: 'Internal Server Error' });
        }
      }
    } finally {
      clearTimeout(timeoutHandle!);
    }
  }
}
