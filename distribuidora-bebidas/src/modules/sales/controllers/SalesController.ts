import { FastifyRequest, FastifyReply } from 'fastify';
import { DynamoDBClient, GetItemCommand, UpdateItemCommand } from '@aws-sdk/client-dynamodb';
import { database } from '../../../shared/database/database';


const dynamoClient = new DynamoDBClient({
  region: process.env.AWS_REGION,
});

const DYNAMO_TABLE = process.env.DYNAMO_TABLE_NAME;

interface SaleRequest {
  productId: string;
  version: number;
}

export class SalesController {
  private pool = database.getPool();
  
  public async create(request: FastifyRequest, reply: FastifyReply): Promise<void> {
    const idempotencyKey = request.headers['x-idempotency-key'] as string;

    if (!idempotencyKey) {
      return reply.status(400).send({ error: 'X-Idempotency-Key header is required' });
    }

    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('TIMEOUT_LIMIT_REACHED')), 5000)
    );

    try {
      await Promise.race([
        this.processSale(request, reply, idempotencyKey),
        timeoutPromise
      ]);
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
    }
  }


  private async processSale(request: FastifyRequest, reply: FastifyReply, idempotencyKey: string): Promise<void> {
    try {
      const getCommand = new GetItemCommand({
        TableName: DYNAMO_TABLE,
        Key: { id: { S: idempotencyKey } },
      });
      const dynamoRes = await dynamoClient.send(getCommand);

      if (dynamoRes.Item) {
        const status = dynamoRes.Item.status?.S;
        const payloadStr = dynamoRes.Item.payload?.S;
        const payload = payloadStr ? JSON.parse(payloadStr) : null;

        if (status === 'COMPLETED' || status === 'FAILED') {
          return reply.status(status === 'COMPLETED' ? 201 : 422).send(payload);
        }
      }
    } catch (err) {
      console.warn('[SalesController] DynamoDB read failed, proceeding to PG:', err);
    }

    const { productId, version } = request.body as SaleRequest;
    const pgClient = await this.pool.connect();

    try {
      await pgClient.query('BEGIN');

      try {
        const updateQuery = `
          UPDATE products 
          SET stock = stock - 1, version = version + 1, updated_at = CURRENT_TIMESTAMP
          WHERE id = $1 AND version = $2 AND stock > 0
          RETURNING id, name, stock, version;
        `;
        const updateRes = await pgClient.query(updateQuery, [productId, version]);

        if (updateRes.rowCount === 0) {
          const errorPayload = { 
            error: 'Unprocessable Entity', 
            message: 'Insufficient stock or product version mismatch' 
          };

          await pgClient.query(
            `INSERT INTO idempotency_outbox (id, status, payload, error_message)
             VALUES ($1, 'FAILED', $2, $3)`,
            [idempotencyKey, JSON.stringify(errorPayload), 'Validation failed']
          );

          await pgClient.query('COMMIT');
          return reply.status(422).send(errorPayload);
        }

        const product = updateRes.rows[0];
        const successPayload = { message: 'Sale completed successfully', product };

        await pgClient.query(
          `INSERT INTO idempotency_outbox (id, status, payload)
           VALUES ($1, 'PROCESSING', $2)`,
          [idempotencyKey, JSON.stringify(successPayload)]
        );

        await pgClient.query('COMMIT');

        setImmediate(async () => {
          try {
            const updateCommand = new UpdateItemCommand({
              TableName: DYNAMO_TABLE,
              Key: { id: { S: idempotencyKey } },
              UpdateExpression: 'SET #st = :status, payload = :payload',
              ExpressionAttributeNames: { '#st': 'status' },
              ExpressionAttributeValues: {
                ':status': { S: 'COMPLETED' },
                ':payload': { S: JSON.stringify(successPayload) },
              },
            });
            await dynamoClient.send(updateCommand);
          } catch (err) {
            console.error('[SalesController] Background DynamoDB update failed:', err);
          }
        });

        return reply.status(201).send(successPayload);

      } catch (innerError: any) {
        if (innerError.code === '23505') {
          await pgClient.query('ROLLBACK');

          const recoveryRes = await this.pool.query(
            'SELECT status, payload FROM idempotency_outbox WHERE id = $1',
            [idempotencyKey]
          );

          if (recoveryRes.rowCount && recoveryRes.rowCount > 0) {
            const { status, payload } = recoveryRes.rows[0];
            const httpCode = (status === 'COMPLETED' || status === 'PROCESSING') ? 201 : 422;
            return reply.status(httpCode).send(payload);
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
