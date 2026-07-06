import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CreateSaleService } from '../../src/modules/sales/services/CreateSaleService';
import { Pool } from 'pg';

// 1. Mock do ProductsRepository como Classe Construtível
const mockUpdateStockAndVersion = vi.fn();
vi.mock('../../src/modules/sales/repositories/ProductsRepository', () => {
  return {
    ProductsRepository: class ProductsRepository {
      updateStockAndVersion = mockUpdateStockAndVersion;
    }
  };
});

// 2. Mock do IdempotencyRepository como Classe Construtível
const mockGetFromDynamo = vi.fn();
const mockGetFromPostgres = vi.fn();
const mockSaveToPostgres = vi.fn();
const mockSaveToDynamoAsync = vi.fn();
vi.mock('../../src/modules/sales/repositories/IdempotencyRepository', () => {
  return {
    IdempotencyRepository: class IdempotencyRepository {
      constructor() {}
      getFromDynamo = mockGetFromDynamo;
      getFromPostgres = mockGetFromPostgres;
      saveToPostgres = mockSaveToPostgres;
      saveToDynamoAsync = mockSaveToDynamoAsync;
    }
  };
});

describe('CreateSaleService', () => {
  let service: CreateSaleService;

  // Mock do cliente Postgres
  const mockPgClient = {
    query: vi.fn(),
    release: vi.fn(),
  };

  // Mock do Pool Postgres
  const mockPool = {
    connect: vi.fn().mockResolvedValue(mockPgClient),
  } as unknown as Pool;

  beforeEach(() => {
    vi.clearAllMocks();
    service = new CreateSaleService(mockPool);
  });

  it('deve retornar o payload cacheado se a transação já foi processada no DynamoDB', async () => {
    const cachedPayload = { message: 'Sale completed successfully', product: { id: 'prod-1', version: 2 } };
    
    mockGetFromDynamo.mockResolvedValue({
      status: 'COMPLETED',
      payload: cachedPayload,
    });

    const result = await service.execute('key-123', 'prod-1', 1);

    expect(result).toEqual({
      source: 'cache',
      status: 'success',
      httpStatus: 201,
      payload: cachedPayload,
    });
    
    // Garante que não abriu conexão com o Postgres
    expect(mockPool.connect).not.toHaveBeenCalled();
  });

  it('deve efetuar a venda com sucesso se não houver cache e o estoque estiver disponível', async () => {
    mockGetFromDynamo.mockResolvedValue(null);

    const mockProduct = { id: 'prod-1', name: 'Cerveja', stock: 9, version: 2 };
    mockUpdateStockAndVersion.mockResolvedValue(mockProduct);

    const result = await service.execute('key-123', 'prod-1', 1);

    expect(result).toEqual({
      source: 'executed',
      status: 'success',
      httpStatus: 201,
      payload: { message: 'Sale completed successfully', product: mockProduct },
    });

    expect(mockPgClient.query).toHaveBeenCalledWith('BEGIN');
    expect(mockUpdateStockAndVersion).toHaveBeenCalledWith(mockPgClient, 'prod-1', 1);
    expect(mockSaveToPostgres).toHaveBeenCalledWith(
      mockPgClient,
      'key-123',
      'PROCESSING',
      { message: 'Sale completed successfully', product: mockProduct }
    );
    expect(mockPgClient.query).toHaveBeenCalledWith('COMMIT');
    expect(mockPgClient.release).toHaveBeenCalled();
  });

  it('deve retornar 422 se o estoque for insuficiente ou houver conflito de versão', async () => {
    mockGetFromDynamo.mockResolvedValue(null);
    mockUpdateStockAndVersion.mockResolvedValue(null);

    const result = await service.execute('key-123', 'prod-1', 1);

    expect(result).toEqual({
      source: 'executed',
      status: 'failed',
      httpStatus: 422,
      payload: {
        error: 'Unprocessable Entity',
        message: 'Insufficient stock or product version mismatch',
      },
    });

    expect(mockPgClient.query).toHaveBeenCalledWith('BEGIN');
    expect(mockSaveToPostgres).toHaveBeenCalledWith(
      mockPgClient,
      'key-123',
      'FAILED',
      expect.any(Object),
      'Validation failed'
    );
    expect(mockPgClient.query).toHaveBeenCalledWith('COMMIT');
    expect(mockPgClient.release).toHaveBeenCalled();
  });

  it('deve retornar o payload cacheado do Postgres se duas requisições colidirem na mesma chave de idempotência (23505)', async () => {
    mockGetFromDynamo.mockResolvedValue(null);

    const duplicateKeyError = { code: '23505' };
    mockUpdateStockAndVersion.mockRejectedValue(duplicateKeyError);

    const cachedPayload = { message: 'Sale completed successfully', product: { id: 'prod-1', version: 2 } };
    mockGetFromPostgres.mockResolvedValue({
      status: 'PROCESSING',
      payload: cachedPayload,
    });

    const result = await service.execute('key-123', 'prod-1', 1);

    expect(result).toEqual({
      source: 'cache',
      status: 'success',
      httpStatus: 201,
      payload: cachedPayload,
    });

    expect(mockPgClient.query).toHaveBeenCalledWith('ROLLBACK');
    expect(mockGetFromPostgres).toHaveBeenCalledWith('key-123');
    expect(mockPgClient.release).toHaveBeenCalled();
  });

  it('deve retornar 422 a partir do cache do Postgres se o registro colidido (23505) tiver falhado', async () => {
    mockGetFromDynamo.mockResolvedValue(null);
    mockUpdateStockAndVersion.mockRejectedValue({ code: '23505' });

    const failedPayload = { error: 'Unprocessable Entity', message: 'Insufficient stock or product version mismatch' };
    mockGetFromPostgres.mockResolvedValue({
      status: 'FAILED',
      payload: failedPayload,
    });

    const result = await service.execute('key-123', 'prod-1', 1);

    expect(result).toEqual({
      source: 'cache',
      status: 'failed',
      httpStatus: 422,
      payload: failedPayload,
    });
  });

  it('deve propagar o erro de colisão (23505) se não houver registro correspondente no Postgres', async () => {
    mockGetFromDynamo.mockResolvedValue(null);
    mockUpdateStockAndVersion.mockRejectedValue({ code: '23505' });
    mockGetFromPostgres.mockResolvedValue(null);

    await expect(service.execute('key-123', 'prod-1', 1)).rejects.toEqual({ code: '23505' });

    expect(mockPgClient.release).toHaveBeenCalled();
  });

  it('deve propagar erros que não sejam de colisão de chave (diferentes de 23505)', async () => {
    mockGetFromDynamo.mockResolvedValue(null);
    const unexpectedError = new Error('Falha inesperada de conexão');
    mockUpdateStockAndVersion.mockRejectedValue(unexpectedError);

    await expect(service.execute('key-123', 'prod-1', 1)).rejects.toThrow('Falha inesperada de conexão');

    expect(mockGetFromPostgres).not.toHaveBeenCalled();
    expect(mockPgClient.release).toHaveBeenCalled();
  });
});
