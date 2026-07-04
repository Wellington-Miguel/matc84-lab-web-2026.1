import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { Pool } from 'pg';
import crypto from 'crypto';
import process from 'process';

vi.hoisted(() => {
  const nativeProcess = globalThis.process;
  
  try {
    nativeProcess.loadEnvFile('.env');
  } catch (err) {
    console.warn('Aviso: Não foi possível carregar o arquivo .env nativamente no bloco hoisted.');
  }

  nativeProcess.env.AWS_ACCESS_KEY_ID = nativeProcess.env.AWS_ACCESS_KEY_ID || 'local';
  nativeProcess.env.AWS_SECRET_ACCESS_KEY = nativeProcess.env.AWS_SECRET_ACCESS_KEY || 'local';
});

import { CreateSaleService } from '../src/modules/sales/services/CreateSaleService';

describe('CreateSaleService - Teste de Concorrência Real (Sem Mocks)', () => {
  let pool: Pool;
  let service: CreateSaleService;
  const testProductId = crypto.randomUUID();

  beforeAll(async () => {
    // Inicializa um Pool real para o ambiente de teste utilizando a URL local
    pool = new Pool({
      connectionString: process.env.DATABASE_URL,
    });
    service = new CreateSaleService(pool);

    // Garante que o produto de teste existe com estoque controlado e versão 1
    await pool.query(
      `INSERT INTO products (id, name, stock, version) 
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (id) DO UPDATE SET stock = $3, version = $4;`,
      [testProductId, 'Cerveja Concorrente Teste', 10, 1]
    );
  });

  afterAll(async () => {
    await pool.query('DELETE FROM idempotency_outbox WHERE payload::text LIKE $1;', [`%${testProductId}%`]);
    await pool.query('DELETE FROM products WHERE id = $1;', [testProductId]);
    await pool.end();
  });

  it('deve processar apenas uma venda com sucesso e rejeitar colisões paralelas de versão (OCC)', async () => {
    const totalRequests = 10;
    const initialVersion = 1;

    // Cria 10 requisições simultâneas, cada uma com uma X-Idempotency-Key nova, mas todas enviando a mesma versão inicial (version: 1)
    const promises = Array.from({ length: totalRequests }).map(() => {
      const uniqueIdempotencyKey = crypto.randomUUID();
      return service.execute(uniqueIdempotencyKey, testProductId, initialVersion);
    });

    // Dispara todas as requisições ao mesmo tempo no banco de dados (Ataque Paralelo)
    const results = await Promise.all(promises);

    const successes = results.filter((r) => r.httpStatus === 201);
    const failures = results.filter((r) => r.httpStatus === 422);

    // Exigimos que EXATAMENTE UMA requisição tenha conseguido dar o UPDATE
    expect(successes.length).toBe(1);

    // Exigimos que todas as outras tenham falhado por conflito de versão
    expect(failures.length).toBe(totalRequests - 1);

    // Verificamos se as falhas retornaram o erro esperado
    expect(failures[0].payload).toEqual({
      error: 'Unprocessable Entity',
      message: 'Insufficient stock or product version mismatch',
    });

    // Faz uma consulta direta no banco físico para checar o estado final do produto
    const productCheck = await pool.query('SELECT stock, version FROM products WHERE id = $1;', [testProductId]);
    const finalProduct = productCheck.rows[0];

    // O estoque deve ter descido exatamente para 9 e a versão subido para 2
    expect(finalProduct.stock).toBe(9);
    expect(finalProduct.version).toBe(2);
  });
});