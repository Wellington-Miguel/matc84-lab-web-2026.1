import { DynamoDBClient, PutItemCommand } from '@aws-sdk/client-dynamodb';
import { database } from '../database/database';

export class IdempotencyWorker {
  private static instance: IdempotencyWorker;
  private isRunning: boolean = false;
  private timer: NodeJS.Timeout | null = null;
  private dynamoClient: DynamoDBClient;
  private tableName: string;
  private intervalMs: number;

  private constructor() {
    const region = process.env.AWS_REGION;
    this.tableName = process.env.DYNAMO_TABLE_NAME || '';

    this.dynamoClient = new DynamoDBClient({
      region: region || 'sa-east-1',
    });
    this.intervalMs = Number(process.env.OUTBOX_WORKER_INTERVAL_MS) || 60000;
  }

  public static getInstance(): IdempotencyWorker {
    if (!IdempotencyWorker.instance) {
      IdempotencyWorker.instance = new IdempotencyWorker();
    }
    return IdempotencyWorker.instance;
  }

  public start(): void {
    if (this.isRunning) {
      console.warn('[IdempotencyWorker] O worker já está em execução.');
      return;
    }

    if (!this.tableName) {
      console.error(
        '[IdempotencyWorker] Erro ao iniciar: DYNAMO_TABLE_NAME não está configurada nas variáveis de ambiente.'
      );
      return;
    }

    this.isRunning = true;
    console.log(`[IdempotencyWorker] Worker iniciado. Intervalo de varredura: ${this.intervalMs}ms`);
    this.scheduleNextRun();
  }

  public stop(): void {
    this.isRunning = false;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    console.log('[IdempotencyWorker] Worker interrompido.');
  }

  private scheduleNextRun(): void {
    if (!this.isRunning) return;

    this.timer = setTimeout(async () => {
      try {
        await this.syncStuckRecords();
      } catch (error) {
        console.error('[IdempotencyWorker] Erro não tratado durante a varredura:', error);
      } finally {
        this.scheduleNextRun();
      }
    }, this.intervalMs);
  }

  public async syncStuckRecords(): Promise<void> {
    const pool = database.getPool();
    const pgClient = await pool.connect();

    try {
      const query = `
        SELECT id, status, payload 
        FROM idempotency_outbox
        WHERE status = 'PROCESSING' 
          AND updated_at < NOW() - INTERVAL '2 minutes'
        LIMIT 50;
      `;

      const result = await pgClient.query(query);

      if (result.rows.length === 0) {
        return;
      }

      console.log(
        `[IdempotencyWorker] Encontrados ${result.rows.length} registros travados em 'PROCESSING'. Sincronizando...`
      );

      for (const row of result.rows) {
        const { id, payload } = row;
        
        const definitiveStatus = 'COMPLETED';

        try {
          const putCommand = new PutItemCommand({
            TableName: this.tableName,
            Item: {
              id: { S: id },
              status: { S: definitiveStatus },
              payload: { S: typeof payload === 'string' ? payload : JSON.stringify(payload) },
            },
          });

          await this.dynamoClient.send(putCommand);

          const updateQuery = `
            UPDATE idempotency_outbox
            SET status = $1, processed_at = CURRENT_TIMESTAMP
            WHERE id = $2;
          `;
          await pgClient.query(updateQuery, [definitiveStatus, id]);

          console.log(`[IdempotencyWorker] Registro ${id} sincronizado no DynamoDB e marcado como concluído no PG.`);
        } catch (itemError) {
          console.error(`[IdempotencyWorker] Falha ao sincronizar o registro ${id}:`, itemError);
        }
      }
    } catch (error) {
      console.error('[IdempotencyWorker] Falha ao ler registros do PostgreSQL:', error);
      throw error;
    } finally {
      pgClient.release();
    }
  }
}
