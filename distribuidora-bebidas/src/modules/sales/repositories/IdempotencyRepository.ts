import { PoolClient, Pool } from 'pg';
import { DynamoDBClient, GetItemCommand, UpdateItemCommand } from '@aws-sdk/client-dynamodb';
import { config } from '../../../config/env';

export interface IdempotencyRecord {
  status: 'PROCESSING' | 'COMPLETED' | 'FAILED';
  payload: any;
  errorMessage?: string;
}

export class IdempotencyRepository {
  private dynamoClient: DynamoDBClient;
  private dynamoTable: string;
  private pgPool: Pool;

  constructor(pgPool: Pool) {
    this.dynamoClient = new DynamoDBClient({
      region: process.env.AWS_REGION || 'sa-east-1',
      ...(config.dynamoEndpoint && { 
        endpoint: config.dynamoEndpoint,
        credentials: { accessKeyId: 'local', secretAccessKey: 'local' } // <--- Adicionado aqui
      }),
    });
    this.dynamoTable = process.env.DYNAMO_TABLE_NAME || '';
    this.pgPool = pgPool;
  }

  // Consulta rápida no DynamoDB
  public async getFromDynamo(key: string): Promise<IdempotencyRecord | null> {
    if (!this.dynamoTable) return null;
    try {
      const getCommand = new GetItemCommand({
        TableName: this.dynamoTable,
        Key: { id: { S: key } },
      });
      const dynamoRes = await this.dynamoClient.send(getCommand);
      if (dynamoRes.Item) {
        const status = dynamoRes.Item.status?.S as any;
        const payloadStr = dynamoRes.Item.payload?.S;
        const payload = payloadStr ? JSON.parse(payloadStr) : null;
        return { status, payload };
      }
    } catch (err) {
      console.warn('[IdempotencyRepository] DynamoDB read failed, proceeding to PG:', err);
    }
    return null;
  }

  // Consulta de fallback no PostgreSQL
  public async getFromPostgres(key: string): Promise<IdempotencyRecord | null> {
    const recoveryRes = await this.pgPool.query(
      'SELECT status, payload, error_message FROM idempotency_outbox WHERE id = $1',
      [key]
    );
    if (recoveryRes.rowCount && recoveryRes.rowCount > 0) {
      const { status, payload, error_message } = recoveryRes.rows[0];
      return { status, payload, errorMessage: error_message };
    }
    return null;
  }

  // Gravação transacional no PostgreSQL
  public async saveToPostgres(
    client: PoolClient,
    key: string,
    status: 'PROCESSING' | 'FAILED',
    payload: any,
    errorMessage?: string
  ): Promise<void> {
    if (status === 'FAILED') {
      await client.query(
        `INSERT INTO idempotency_outbox (id, status, payload, error_message)
         VALUES ($1, 'FAILED', $2, $3)`,
        [key, JSON.stringify(payload), errorMessage || null]
      );
    } else {
      await client.query(
        `INSERT INTO idempotency_outbox (id, status, payload)
         VALUES ($1, 'PROCESSING', $2)`,
        [key, JSON.stringify(payload)]
      );
    }
  }

  // Sincronização em background no DynamoDB
  public async saveToDynamoAsync(key: string, status: 'COMPLETED' | 'FAILED', payload: any): Promise<void> {
    if (!this.dynamoTable) return;
    try {
      const updateCommand = new UpdateItemCommand({
        TableName: this.dynamoTable,
        Key: { id: { S: key } },
        UpdateExpression: 'SET #st = :status, payload = :payload',
        ExpressionAttributeNames: { '#st': 'status' },
        ExpressionAttributeValues: {
          ':status': { S: status },
          ':payload': { S: JSON.stringify(payload) },
        },
      });
      await this.dynamoClient.send(updateCommand);
    } catch (err) {
      console.error('[IdempotencyRepository] Background DynamoDB update failed:', err);
    }
  }

  // Busca os últimos 50 registros do outbox para inspeção visual
  public async getAllFromPostgres(): Promise<any[]> {
    const res = await this.pgPool.query(
      'SELECT id, status, payload, error_message, updated_at FROM idempotency_outbox ORDER BY updated_at DESC LIMIT 50;'
    );
    return res.rows;
  }
}
