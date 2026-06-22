import { describe, it, expect, vi, beforeEach } from 'vitest';

// Usa vi.hoisted para declarar a variável mockExecute de forma que ela seja içada (hoisted) junto com o vi.mock
const { mockExecute } = vi.hoisted(() => {
  return { mockExecute: vi.fn() };
});

vi.mock('../../src/modules/sales/services/CreateSaleService', () => {
  return {
    CreateSaleService: class CreateSaleService {
      execute = mockExecute;
    }
  };
});

// Importação do app precisa vir depois da declaração do vi.mock
import { app } from '../../src/app';

describe('POST /v1/sales - Integração HTTP', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('deve retornar 400 se o header x-idempotency-key não for enviado', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/v1/sales',
      payload: {
        productId: 'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
        version: 1,
      },
    });

    expect(response.statusCode).toBe(400);
    const body = JSON.parse(response.body);
    expect(body.error).toBe('Bad Request');
    expect(body.message).toContain('validação');
  });

  it('deve retornar 400 se o header x-idempotency-key não for um UUID válido', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/v1/sales',
      headers: {
        'x-idempotency-key': 'chave-invalida-nao-uuid',
      },
      payload: {
        productId: 'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
        version: 1,
      },
    });

    expect(response.statusCode).toBe(400);
  });

  it('deve retornar 400 se o productId não for um UUID válido', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/v1/sales',
      headers: {
        'x-idempotency-key': 'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
      },
      payload: {
        productId: 'invalido',
        version: 1,
      },
    });

    expect(response.statusCode).toBe(400);
  });

  it('deve retornar 400 se a version for menor que 1', async () => {
    const response = await app.inject({
      method: 'POST',
      url: '/v1/sales',
      headers: {
        'x-idempotency-key': 'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
      },
      payload: {
        productId: 'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
        version: 0,
      },
    });

    expect(response.statusCode).toBe(400);
  });

  it('deve retornar 201 e efetuar a venda se todos os parâmetros forem válidos', async () => {
    const successPayload = { message: 'Sale completed successfully', product: {} };
    
    mockExecute.mockResolvedValue({
      source: 'executed',
      status: 'success',
      httpStatus: 201,
      payload: successPayload,
    });

    const response = await app.inject({
      method: 'POST',
      url: '/v1/sales',
      headers: {
        'x-idempotency-key': 'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
      },
      payload: {
        productId: 'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
        version: 1,
      },
    });

    expect(response.statusCode).toBe(201);
    expect(JSON.parse(response.body)).toEqual(successPayload);
    expect(mockExecute).toHaveBeenCalledWith(
      'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
      'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
      1
    );
  });
});
