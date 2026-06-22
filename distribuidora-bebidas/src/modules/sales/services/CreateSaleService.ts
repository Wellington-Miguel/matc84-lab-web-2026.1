import { Pool } from 'pg';
import { ProductsRepository } from '../repositories/ProductsRepository';
import { IdempotencyRepository } from '../repositories/IdempotencyRepository';

export interface CreateSaleResult {
  source: 'cache' | 'executed';
  status: 'success' | 'failed';
  httpStatus: 201 | 422;
  payload: any;
}

export class CreateSaleService {
  private pgPool: Pool;
  private productsRepository: ProductsRepository;
  private idempotencyRepository: IdempotencyRepository;

  constructor(pgPool: Pool) {
    this.pgPool = pgPool;
    this.productsRepository = new ProductsRepository();
    this.idempotencyRepository = new IdempotencyRepository(pgPool);
  }

  public async execute(idempotencyKey: string, productId: string, version: number): Promise<CreateSaleResult> {
    // 1. Verificar idempotência no DynamoDB (Fast-path)
    const cachedRecord = await this.idempotencyRepository.getFromDynamo(idempotencyKey);
    if (cachedRecord) {
      return {
        source: 'cache',
        status: cachedRecord.status === 'COMPLETED' ? 'success' : 'failed',
        httpStatus: cachedRecord.status === 'COMPLETED' ? 201 : 422,
        payload: cachedRecord.payload,
      };
    }

    const pgClient = await this.pgPool.connect();

    try {
      await pgClient.query('BEGIN');

      try {
        // 2. Tentar atualizar o produto usando controle de concorrência otimista (OCC)
        const product = await this.productsRepository.updateStockAndVersion(pgClient, productId, version);

        if (!product) {
          const errorPayload = { 
            error: 'Unprocessable Entity', 
            message: 'Insufficient stock or product version mismatch' 
          };

          // Grava a falha no outbox transacionalmente
          await this.idempotencyRepository.saveToPostgres(pgClient, idempotencyKey, 'FAILED', errorPayload, 'Validation failed');
          await pgClient.query('COMMIT');

          return {
            source: 'executed',
            status: 'failed',
            httpStatus: 422,
            payload: errorPayload,
          };
        }

        const successPayload = { message: 'Sale completed successfully', product };

        // Grava o processamento no outbox transacionalmente
        await this.idempotencyRepository.saveToPostgres(pgClient, idempotencyKey, 'PROCESSING', successPayload);
        await pgClient.query('COMMIT');

        // 3. Salvar no DynamoDB de forma assíncrona em background
        setImmediate(async () => {
          await this.idempotencyRepository.saveToDynamoAsync(idempotencyKey, 'COMPLETED', successPayload);
        });

        return {
          source: 'executed',
          status: 'success',
          httpStatus: 201,
          payload: successPayload,
        };

      } catch (innerError: any) {
        await pgClient.query('ROLLBACK');

        // Tratamento de concorrência na chave única (duplicidade no insert de idempotência no Postgres)
        if (innerError.code === '23505') {
          const pgCachedRecord = await this.idempotencyRepository.getFromPostgres(idempotencyKey);
          if (pgCachedRecord) {
            const httpCode = (pgCachedRecord.status === 'COMPLETED' || pgCachedRecord.status === 'PROCESSING') ? 201 : 422;
            return {
              source: 'cache',
              status: (pgCachedRecord.status === 'COMPLETED' || pgCachedRecord.status === 'PROCESSING') ? 'success' : 'failed',
              httpStatus: httpCode,
              payload: pgCachedRecord.payload,
            };
          }
        }
        throw innerError;
      }
    } catch (error) {
      await pgClient.query('ROLLBACK');
      throw error;
    } finally {
      pgClient.release();
    }
  }
}
