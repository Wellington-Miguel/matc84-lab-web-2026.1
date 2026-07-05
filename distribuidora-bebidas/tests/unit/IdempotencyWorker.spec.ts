import { describe, it, expect, vi, beforeEach } from 'vitest';

// 1. Mock do cliente DynamoDB
const mockSend = vi.fn();
vi.mock('@aws-sdk/client-dynamodb', () => {
  return {
    DynamoDBClient: class DynamoDBClient {
      send = mockSend;
    },
    PutItemCommand: class PutItemCommand {
      constructor(public input: any) {}
    },
  };
});

// 2. Mock do Pool/Client Postgres via singleton `database`
const mockQuery = vi.fn();
const mockRelease = vi.fn();
const mockConnect = vi.fn().mockResolvedValue({ query: mockQuery, release: mockRelease });
vi.mock('../../src/shared/database/database', () => {
  return {
    database: {
      getPool: () => ({ connect: mockConnect }),
    },
  };
});

// 3. Mock da configuração (evita depender de variáveis de ambiente reais)
vi.mock('../../src/config/env', () => {
  return {
    config: {
      dynamoTableName: 'sales-idempotency-dev',
      awsRegion: 'sa-east-1',
      dynamoEndpoint: undefined,
      outboxWorkerIntervalMs: 60000,
    },
  };
});

import { IdempotencyWorker } from '../../src/shared/services/IdempotencyWorker';

describe('IdempotencyWorker', () => {
  let worker: IdempotencyWorker;

  beforeEach(() => {
    vi.clearAllMocks();
    worker = IdempotencyWorker.getInstance();
  });

  it('reutiliza a mesma instância (singleton)', () => {
    expect(IdempotencyWorker.getInstance()).toBe(worker);
  });

  it('não consulta o DynamoDB quando não há registros travados em PROCESSING', async () => {
    mockQuery.mockResolvedValueOnce({ rows: [] });

    await worker.syncStuckRecords();

    expect(mockSend).not.toHaveBeenCalled();
    expect(mockRelease).toHaveBeenCalledTimes(1);
  });

  it('sincroniza um registro travado com o DynamoDB e marca como COMPLETED no Postgres', async () => {
    mockQuery
      .mockResolvedValueOnce({ rows: [{ id: 'key-1', status: 'PROCESSING', payload: { foo: 'bar' } }] })
      .mockResolvedValueOnce({});
    mockSend.mockResolvedValueOnce({});

    await worker.syncStuckRecords();

    expect(mockSend).toHaveBeenCalledTimes(1);
    expect(mockQuery).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining('UPDATE idempotency_outbox'),
      ['COMPLETED', 'key-1']
    );
    expect(mockRelease).toHaveBeenCalledTimes(1);
  });

  it('mantém um registro em PROCESSING e segue para os demais quando o DynamoDB falha', async () => {
    mockQuery.mockResolvedValueOnce({
      rows: [
        { id: 'key-1', status: 'PROCESSING', payload: { foo: 'bar' } },
        { id: 'key-2', status: 'PROCESSING', payload: { foo: 'baz' } },
      ],
    });
    mockQuery.mockResolvedValue({});
    mockSend
      .mockRejectedValueOnce(new Error('DynamoDB indisponível'))
      .mockResolvedValueOnce({});

    await expect(worker.syncStuckRecords()).resolves.toBeUndefined();

    expect(mockSend).toHaveBeenCalledTimes(2);

    const updateCalls = mockQuery.mock.calls.filter(
      (call) => typeof call[0] === 'string' && call[0].includes('UPDATE idempotency_outbox')
    );
    expect(updateCalls).toHaveLength(1);
    expect(updateCalls[0][1]).toEqual(['COMPLETED', 'key-2']);
    expect(mockRelease).toHaveBeenCalledTimes(1);
  });

  it('libera a conexão e propaga o erro se a consulta ao Postgres falhar', async () => {
    mockQuery.mockRejectedValueOnce(new Error('Conexão perdida'));

    await expect(worker.syncStuckRecords()).rejects.toThrow('Conexão perdida');
    expect(mockRelease).toHaveBeenCalledTimes(1);
  });
});
